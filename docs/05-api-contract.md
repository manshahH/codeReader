# Code Reading App : MVP API Contract (v1)

Base URL: `https://api.<domain>/v1`
All responses are JSON. All timestamps are ISO 8601 UTC.

---

## 1. Conventions

### Authentication
- `Authorization: Bearer <access_jwt>` on every endpoint except auth and health.
- Access JWT lifetime 15 min. Claims: `sub` (user id), `plan` (always `free` at MVP), `exp`, `iat`, `jti`. Nothing else.
- Refresh token: opaque, `HttpOnly; Secure; SameSite=Lax` cookie named `rt`, path-scoped to `/v1/auth/refresh`. Rotated on every refresh.

### Errors (uniform shape)
```json
{
  "error": {
    "code": "exercise_not_in_session",
    "message": "This exercise is not part of your current session.",
    "request_id": "req_8f2a1c"
  }
}
```
| HTTP | code (examples) | meaning |
|------|-----------------|---------|
| 400  | `validation_error` | malformed body/params |
| 401  | `invalid_token`, `token_expired` | re-auth / refresh |
| 403  | `forbidden` | authenticated but not allowed |
| 404  | `not_found` | |
| 409  | `already_attempted`, `idempotency_conflict` | duplicate submit with different body |
| 422  | `answer_shape_mismatch` | answer doesn't match exercise type |
| 429  | `rate_limited` | includes `Retry-After` |
| 500/503 | `internal`, `grading_unavailable` | |

### Rate limits (Redis token bucket, per user; per IP pre-auth)
| Scope | Limit |
|---|---|
| default | 60 req/min |
| `POST /attempts` | 10 req/min |
| auth endpoints | 10 req/min per IP |

Headers on every response: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After` on 429.

### Idempotency
`POST /attempts` requires header `Idempotency-Key: <uuid>` (client-generated per exercise serve). Replays within 24h return the original response with `X-Idempotent-Replay: true`. Same key with a different body -> `409 idempotency_conflict`.

---

## 2. Auth

### `GET /auth/github/start`
Begins OAuth (Authorization Code + PKCE).
- Server generates `state` (single-use, Redis, 10 min TTL) and PKCE verifier/challenge.
- `302` to GitHub authorize URL with `scope=read:user`.

### `GET /auth/github/callback?code=&state=`
- Validates `state` (consume-once), exchanges code (with PKCE verifier), fetches profile with `read:user`.
- Upserts `users` + `auth_identities` (GitHub token encrypted at rest, never returned).
- Sets `rt` cookie, then `302` to the SPA (`https://app.<domain>/welcome`). **No tokens ever appear in URLs.**
- SPA immediately calls `POST /auth/refresh` to obtain its first access token.

Failure modes: invalid/expired state -> `302` to SPA `/login?error=oauth_state`; GitHub error passthrough -> `/login?error=oauth_denied`.

### `POST /auth/refresh`
Cookie-authenticated. Rotates the refresh token (old row gets `rotated_at`; same `family_id`), sets the new cookie.
```json
200
{
  "access_token": "eyJ...",
  "expires_in": 900,
  "user": { "id": "u_...", "username": "mohsin", "display_name": null,
            "avatar_url": "https://...", "level": "mid", "timezone": "Asia/Karachi",
            "onboarded": true }
}
```
Reuse of a rotated/revoked token -> `401 invalid_token` + server-side alert (family kill is post-MVP).

### `POST /auth/logout`
Revokes the presented refresh token family, clears cookie. `204`.

---

## 3. Me

### `GET /me`
Profile + settings. Same `user` object as above plus `reminder_local_time`.

### `PATCH /me`
Body (all optional): `display_name`, `timezone` (IANA, validated), `level`, `reminder_local_time` (`"08:00"` or `null`).
`200` with updated user. Changing `timezone` never retroactively breaks a streak (reconciliation job handles the boundary day).

### `GET /me/stats`
```json
{
  "current_streak": 12,
  "longest_streak": 30,
  "streak_freezes": 1,
  "total_attempts": 240,
  "total_correct": 181,
  "accuracy_by_type": { "spot_the_bug": 0.71, "trace": 0.83, "summarize": 0.66 },
  "last_active_local_date": "2026-07-06"
}
```

### `GET /me/concepts`
Skill graph. `[{ "concept": "mutable-default-arg", "mastery": 0.62, "attempts": 9, "next_review_at": "2026-07-09T00:00:00Z" }, ...]` sorted weakest-first.

---

## 4. Daily session (the core loop)

### `GET /session/today`
Returns today's session in the user's timezone. First call of the day samples it (spaced-repetition due -> curriculum sampler -> one boss slot), persists to `daily_sessions`, caches in Redis. Later calls return the identical session with progress merged in.

```json
{
  "session_date": "2026-07-06",
  "completed": false,
  "exercises": [
    {
      "slot": 1,
      "exercise_id": "9f3a7c...",
      "version": 3,
      "type": "spot_the_bug",
      "language": "python",
      "difficulty_band": "medium",
      "est_time_s": 90,
      "is_boss": false,
      "attempted": false,
      "payload": {
        "code": "def add_item(item, bucket=[]):\n ...",
        "context_note": "Part of a cart service. Called per request.",
        "answer_mode": "line_select_plus_reason",
        "reason_options": [
          { "id": "a", "text": "Mutable default argument shared across calls" },
          { "id": "b", "text": "append returns None so the return value is wrong" },
          { "id": "c", "text": "bucket is shadowed by the parameter" },
          { "id": "d", "text": "No bug; this is correct" }
        ]
      }
    }
  ]
}
```

Guarantees:
- `payload` only. `grading` and `explanation` are structurally absent (serializer allowlist + CI leak test).
- Exact difficulty numbers are internal; clients get `difficulty_band` (`easy|medium|hard|boss`).
- If the LLM grader is degraded, `summarize` slots are replaced at sampling time; already-issued sessions are unchanged.

There is **no** standalone `GET /exercises/{id}` at MVP. The session is the only content channel: fewer scraping surfaces, and the "not in your session" rule below stays enforceable.

---

## 5. Attempts

### `POST /attempts`
Headers: `Idempotency-Key` (required).
```json
{
  "exercise_id": "9f3a7c...",
  "exercise_version": 3,
  "answer": { "line": 1, "reason_id": "a" },
  "time_taken_ms": 48200
}
```
Answer shapes by type (validated server-side, else `422`):
| type | answer |
|---|---|
| `spot_the_bug` | `{ "line": int, "reason_id": string }` |
| `trace` | `{ "choice_id": string }` |
| `summarize` | `{ "text": string }` (<= 60 words) |

Rules: exercise must be in today's uncompleted session for this user (else `403 exercise_not_in_session`); one graded attempt per exercise per session (else `409 already_attempted`).

**Deterministic types -> `200` synchronously:**
```json
{
  "attempt_id": 481923,
  "status": "graded",
  "is_correct": true,
  "reveal": {
    "correct_lines": [1],
    "correct_reason_id": "a",
    "explanation": {
      "summary": "Default arguments are evaluated once at definition time...",
      "principle": "Never use mutable default arguments.",
      "line_notes": [{ "line": 1, "note": "bucket=[] is created once and shared." }]
    }
  },
  "percentile": { "solve_rate": 0.31, "n": 412 },        // null until n >= 30
  "streak": { "current": 13, "event": "extended" },       // null if already counted today
  "session": { "completed": false, "remaining": 2 }
}
```

**`summarize` -> synchronous inline grading (6s budget):** same `200` shape, plus:
```json
"score": 0.7,
"grader_output": {
  "rubric_hits":   ["retries with exponential backoff", "only retries network errors"],
  "rubric_misses": ["re-raises after final attempt"],
  "reference_answer": "Retries the wrapped call up to N times..."
}
```
LLM timeout/failure -> `200` with `"status": "grading_pending"`, no reveal yet; a cron retries; client polls `GET /attempts/{id}`. Streak still counts (the user did the work; grading latency is our problem, not theirs).

### `GET /attempts/{id}`
Own attempts only. Returns the same grade shape; `grading_pending` until resolved. Poll interval hint: `Retry-After: 3`.

---

## 6. Disputes

### `POST /exercises/{exercise_id}/v/{version}/dispute`
```json
{ "reason": "wrong_answer", "body": "The fix on line 4 also changes behavior when...", "attempt_id": 481923 }
```
`201 { "dispute_id": 88, "status": "open" }`. One open dispute per user per exercise version. Fires an operator alert; pulling the exercise is a manual admin action at MVP.

---

## 7. Ops

### `GET /healthz` (public)
`200 { "status": "ok" }` : checks DB and Redis connectivity. LLM provider health is reported in metrics, not here (its failure degrades, not downs, the app).

Admin/review endpoints (`/admin/*`) are a separate internal app behind its own auth; deliberately out of this public contract.

---

## 8. Contract-level invariants (CI-enforced)

1. No response serializes `grading` or `explanation` before a graded attempt exists (leak test greps serialized session bundles).
2. Exercises are immutable per version; any reveal content is tied to `(exercise_id, version)`.
3. `POST /attempts` is idempotent per key; identical replays are byte-identical responses.
4. All state-changing endpoints require the access JWT; the refresh cookie alone can only hit `/auth/refresh` and `/auth/logout`.
5. Streak transitions always produce a `streak_events` row.
