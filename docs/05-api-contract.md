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

Failure modes: invalid/expired state -> `302` to SPA `/login?error=oauth_state`; GitHub error passthrough -> `/login?error=oauth_denied`; authenticated GitHub identity not on the beta allowlist (`users.beta_allowed=false`, M8 D-78) -> `302` to SPA `/login?error=beta_required`, no `rt` cookie set (the `users`/`auth_identities` upsert is still committed, so an admin can grant access by username without a second login).

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

### Email capture (A2, D-120)

The `user` object above carries three email fields: `email` (the VERIFIED
address, or `null`), `email_verified` (bool), and `pending_email` (an address
awaiting confirmation, or `null`). `email` only ever holds a verified address,
so adding or changing one never takes the current one offline: the new address
waits in `pending_email` and the old one keeps receiving until the new one is
confirmed. A typo therefore cannot silently kill the notification channel, and
A3 always sees either a deliverable address or none.

`email_verified_at` and anything from `email_verification_tokens` are NOT
exposed. Email does **not** go through `PATCH /me`: it needs issue-send-confirm
semantics that a partial update cannot express.

Throttled per user AND per target address (`EMAIL_VERIFICATION_RESEND_COOLDOWN_S`
floor between sends, `EMAIL_VERIFICATION_SENDS_PER_HOUR` cap). Either one denying
is a `429 rate_limited` with `Retry-After`.

All four routes return the same body, the email slice of the user object:
```json
{ "email": "dev@example.com", "email_verified": true, "pending_email": null }
```

#### `POST /me/email`
Body: `{ "email": "dev@example.com" }`. Sets or replaces `pending_email`,
invalidates the user's outstanding tokens, issues a new one, and sends the
verification link.

The response is **identical whether or not the address is already verified on
another account**. We never check, because behaving differently is itself the
disclosure. The partial unique index settles the conflict at verify time.

`400 validation_error` for a malformed address (validated strictly; anything
containing CR, LF, NUL or any other control character is refused outright, never
sanitized). `409 email_already_verified` only when the address is already
confirmed **on the caller's own account**.

#### `POST /me/email/verify`
Body: `{ "token": "..." }`. Consumes the token, promotes the address **the token
was issued for** (not whatever `pending_email` currently says, so a stale link
can never promote a newer address), stamps `email_verified_at`, and clears
`pending_email`.

`400 verification_failed` is the **single** response for every failure: unknown
token, expired token, already-consumed token, token invalidated by a newer
issue, a token belonging to another user, and losing the uniqueness race to an
account that verified the same address first. Distinguishing them is an oracle.

#### `POST /me/email/resend`
Reissues for the pending address, subject to the same throttle. Issuing a new
token invalidates the previous one. `409 no_pending_email` when nothing is
pending.

#### `DELETE /me/email`
Clears `email`, `email_verified_at` and `pending_email`, and invalidates
outstanding tokens, in one transaction. Consent that cannot be withdrawn
in-product is not consent.

Verification links are built from `APP_ORIGIN`, never from a request header.

### `GET /me/stats`
```json
{
  "current_streak": 12,
  "longest_streak": 30,
  "streak_freezes": 1,
  "total_attempts": 240,
  "total_correct": 181,
  "accuracy_by_type": { "spot_the_bug": 0.71, "trace": 0.83, "summarize": 0.66 },
  "last_active_local_date": "2026-07-06",
  "total_sessions": 41,
  "repair_available": false,
  "repair_restores_to": null
}
```
`streak_freezes` is the A1 freeze balance (docs/10; D-116). `repair_available`
and `repair_restores_to` are computed per request, never stored: available is
true when the most recent `reset` is still inside `STREAK_REPAIR_WINDOW_H` and
has not already been repaired, and `repair_restores_to` is the value a repair
would restore (the N in "Restore your N-day streak"), or `null` when no repair
is available. `repair_available == (repair_restores_to is not null)` always. The
payload is an allowlist; these are the only streak fields it carries.

### `POST /streak/repair`
Restores the streak lost at the most recent repairable reset. Requires an
`Idempotency-Key` header, same discipline as `POST /attempts` (own namespace;
replays return the cached, byte-identical success).
```json
{ "current_streak": 13, "repaired": true }
```
The restored value is the unbroken counterfactual, computed entirely from the
`streak_events` ledger: `reset.from_value` (the value lost) plus the post-reset
run length, read as the `to_value` of the most recent transition row. It is NOT
`reset.from_value` plus elapsed days: the reset day is itself an active day (a
`reset` row is only ever written on a submit), so elapsed-day arithmetic drops
that day's credit, and it also over-credits any day the user was not active.
The live `current_streak` is never read, since later submits may have changed it.

Serialized under a per-`(user, "streak_repair")` `pg_advisory_xact_lock`
(D-104's lock class): the idempotency reservation is per-key, so two concurrent
requests with different `Idempotency-Key`s would otherwise both read the same
unrepaired reset and both restore it.
`409 not_repairable` when there is no reset, when it is outside the window, or
when that reset has already been repaired (a reset is repairable at most once).
`400` when the `Idempotency-Key` header is missing.

### `GET /me/concepts`
Skill graph. `[{ "concept": "mutable-default-arg", "mastery": 0.62, "attempts": 9, "next_review_at": "2026-07-09T00:00:00Z" }, ...]` sorted weakest-first.

### `GET /me/activity?from=&to=`
Contribution-grid data (D-94). Both params optional; default window is the 365 days ending "today" in the user's own timezone.
```json
[
  { "session_date": "2026-07-05", "completed": true },
  { "session_date": "2026-07-06", "completed": false }
]
```
One entry per `daily_sessions` row in range -- a date with no entry means the user never opened the app that day. `completed: false` means opened but not finished.

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

### `GET /session/today/review`
"Review today's session" (D-97). Every exercise from today's session the user has already submitted an answer for -- their answer, the verdict, and the full reveal, reusing `build_reveal`/`build_summarize_reveal` verbatim (the same builders `POST /attempts`/`GET /attempts/{id}` call). Unattempted exercises are omitted.
```json
{
  "session_date": "2026-07-06",
  "exercises": [
    {
      "slot": 1,
      "exercise_id": "9f3a7c...",
      "version": 3,
      "type": "spot_the_bug",
      "concepts": ["mutable-default-arg"],
      "code": "def add_item(item, bucket=[]):\n ...",
      "context_note": "Part of a cart service.",
      "answer": { "line": 1, "reason_id": "a" },
      "verdict": "correct",
      "reveal": { "correct_lines": [1], "correct_reason_id": "a", "explanation": { "...": "..." } }
    }
  ]
}
```
`verdict` is one of `correct | incorrect | skipped | grading_pending | grading_failed`.

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
| `predict_the_fix` | `{ "choice_id": string }` |
| `summarize` | `{ "text": string }` (<= 60 words) |

**"I don't know" (D-93):** for `spot_the_bug`/`trace`/`predict_the_fix` only (not `summarize`), `{ "skipped": true }` is also accepted -- its own exact-key-set branch, not a relaxation of the shapes above. Returns `"status": "skipped"`, `"is_correct": null`, and the full `reveal` (it still teaches, per docs/08's copy voice: the app never scolds).

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
  "session": { "completed": false, "remaining": 2, "first_completed_session": false }
}
```
`session.first_completed_session` (D-95) is `true` only on the single attempt response that both completes today's session AND is the user's first-ever completed daily session -- the client's cue to show the beta review prompt (section 6). It is computed once, at the moment `daily_sessions.completed_at` is set; a byte-identical idempotency replay of that same request still carries `true` (it's the cached body), but no other request ever recomputes it, so it is `false` everywhere else.

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

## 6. Reviews (beta feedback)

### `POST /me/review`
Upsert (D-96): one review per user, enforced by a DB-level UNIQUE on `user_id`. Safe to call more than once; each call replaces the previous review.
```json
{ "rating": 5, "body": "Wish I'd had this in my first year." }
```
`200` with the stored review (`rating`, `body`, `created_at`, `updated_at`).

### `GET /me/review`
`200 { "reviewed": true, "review": { "rating": 5, "body": "...", "created_at": "...", "updated_at": "..." } }` or `{ "reviewed": false, "review": null }`. The client's cue to never show the review prompt twice.

---

## 7. Disputes

### `POST /exercises/{exercise_id}/v/{version}/dispute`
```json
{ "reason": "wrong_answer", "body": "The fix on line 4 also changes behavior when...", "attempt_id": 481923 }
```
`201 { "dispute_id": 88, "status": "open" }`. One open dispute per user per exercise version. Fires an operator alert; pulling the exercise is a manual admin action at MVP.

---

## 8. Ops

### `GET /healthz` (public)
`200 { "status": "ok" }` : checks DB and Redis connectivity. LLM provider health is reported in metrics, not here (its failure degrades, not downs, the app).

Admin/review endpoints (`/admin/*`) are a separate internal app behind its own auth; deliberately out of this public contract. `GET /admin/reviews` (D-96) lists every submitted review, gated by the same `X-Admin-Token` shared secret as the rest of `/admin/*`.

`POST /admin/streak/outage-freeze { "local_date": "2026-07-17" }` (A1, the "big
red button") covers that local date for every user with recorded activity,
writing one `freeze_used` row with `note: 'outage'` per user. It spends no
balance and mutates no `current_streak`: it is a pure ledger write, and the
protection is realized at each user's next submit through the D-116 covered-day
rule. Users who already have a `freeze_used` row for the date are skipped, so
re-running it for the same date is a no-op. Returns
`{ "local_date": ..., "users_covered": N }`.

`POST /admin/streak/grant-initial-freezes { "local_date": "2026-07-18" }`
(D-118) is the one-time A1 backfill: accounts whose `user_stats` row predates
A1 sit at `streak_freezes = 0`, because the starting grant happens at row
creation. Raises them to `min(STREAK_FREEZE_START, STREAK_FREEZE_MAX)`, never
lowers a balance, never touches `current_streak`, and writes one `adjusted` row
per granted user carrying the `[a1:initial-grant]` marker. Idempotent on both
the balance and that marker, so a re-run reports `granted_to: 0` even for users
who have since spent their freezes. Run once after deploy. Returns
`{ "granted_to": N, "balance": 2 }`.

---

## 9. Contract-level invariants (CI-enforced)

1. No response serializes `grading` or `explanation` before a graded attempt exists (leak test greps serialized session bundles).
2. Exercises are immutable per version; any reveal content is tied to `(exercise_id, version)`.
3. `POST /attempts` is idempotent per key; identical replays are byte-identical responses.
4. All state-changing endpoints require the access JWT; the refresh cookie alone can only hit `/auth/refresh` and `/auth/logout`.
5. Streak transitions always produce a `streak_events` row.
