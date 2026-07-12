# CodeReader Red-Team Findings — Phase 1 (FIND)

Engagement: pre-soft-launch red team. **Phase 1 only: no source files changed.**
All findings below were derived from reading the code and, where marked
`[verified]`, confirmed by a live probe against the running stack
(api/postgres/redis up) or a read-only SQL query. Nothing has been fixed;
awaiting triage on which to fix and in what order.

## Phase 0 — backup

- Fresh backup taken before any probing:
  `backend/data/backups/codereader_2026-07-12T2030Z.dump` (174 KB, custom-format
  pg_dump via `POSTGRES_CONTAINER=codereader-postgres-1`).
- Baseline captured: **105 exercises** (25 live), **22 users**, **68 attempts**.
- All probing was read-only or used minted access tokens for existing users; no
  rows were written, updated, or deleted. A second backup will be taken before
  any Phase 2 fix batch.

---

## Severity-ranked summary

| ID | Sev | Surface | One-line |
|----|-----|---------|----------|
| **C1** | Critical | D content | Every `trace` exercise's correct answer is choice `a` / always first — the whole type is gameable without reading code `[verified]` |
| **C2** | Critical | E frontend | No React error boundary anywhere + reveal views dereference unguarded server shapes → one bad grade white-screens the entire app |
| **H1** | High | F concurrency | Attempt advisory lock is keyed per-exercise, so two concurrent first-of-day submits of *different* exercises double-write `streak_events` (invariant-5 breach) and lose a `total_attempts` increment `[verified: no unique constraint]` |
| **H2** | High | E frontend | Onboarding gate is not enforced on deep-links; un-onboarded users reach `/session`/`/profile`/`/review` directly |
| **M1** | Medium | G config | Unhandled 500s render as plain-text `Internal Server Error` — no uniform JSON body, no `request_id`, no security/rate-limit headers on the error path `[verified]` |
| **M2** | Medium | F ratelimit | Unauthenticated flood of `POST /v1/attempts` hits no rate limiter at all (endpoint exempt from default middleware; own limiter is post-auth) `[verified: 15×401, 0×429]` |
| **M3** | Medium | G config | Client-supplied `X-Request-ID` is trusted, reflected in the body, and injected into structured logs + Sentry tags → log forging / correlation-id spoofing `[verified]` |
| **M4** | Medium | B/D content | Content volume: only ~21 deterministic live exercises; a daily user exhausts fresh content in days and the sampler silently re-serves seen exercises |
| **M5** | Medium | F resilience | A Redis outage 500s every non-exempt route (fail-closed, no degradation) — the entire authenticated API depends on Redis being up |
| **M6** | Medium | E frontend | Dashboard/Profile use `Promise.all`; one failing analytics endpoint blanks the whole page instead of degrading a section |
| **M7** | Medium | A auth | OAuth callback `state` is single-use in Redis but not bound to the initiating browser → login-CSRF (victim gets logged into attacker's account) |
| **M8** | Medium | F jobs | `grading_retry` batch aborts and rolls back all progress on any non-`RubricGrading*` exception; a poison `grading_pending` row re-aborts every tick |
| **M9** | Medium | E frontend | Reveal/Review views throw on a partial `reveal` shape; background token-refresh failure hard-logs-out mid-session; invalid server timezone throws in render (all amplified to full white-screen by C2) |
| **L1** | Low | A/IDOR | Dispute `attempt_id` soft-link is stored unvalidated — can reference another user's or a nonexistent attempt |
| **L2** | Low | A | Any existing exercise version can be disputed without ever attempting it (spam surface, bounded by one-open-per-version) |
| **L3** | Low | G config | `JWT_SECRET` is 24 chars in this deployment; `config.py` enforces only `min_length=1` |
| **L4** | Low | F streak | Repeated westward timezone changes can inflate a streak (~+2/real-day) via the reconcile clamp |
| **L5** | Low | B | No request-body size limit; `answer` is `dict[str, Any]` with unbounded value sizes → DB/memory bloat vector |
| **L6** | Low | E a11y | Modals lack focus trap/restore; gutter line-select creates one tab stop per code line |
| **L7** | Low | E | Idempotency key is per-`exercise_id` for the JS module lifetime (not per serve); double-submit can double-count the local tally |
| **L8** | Low | D | Latent: `payload.choices` stores `misconception` (null on the correct choice) in the DB; not leaked today (allowlist strips it), defense-in-depth risk |
| **L9** | Low | D | D-90 fallout: 5 `in_review` llm STB lost `fixed_code` (hash only) → cannot be derived into predict_the_fix; no live impact |
| **L10** | Low | F | `hashtext` advisory-lock collisions over-serialize unrelated submits (correctness-safe, throughput only) |

Detail for each below. A closing section lists surfaces **verified robust** so the
report is not read as "everything is broken."

---

## CRITICAL

### C1 — Every `trace` exercise is gameable: correct answer is always choice `a` / first `[verified]`

- **Severity:** Critical (scoring + learning integrity defeated for an entire live exercise type).
- **Reproduction (verified against live DB and the live API):**
  ```
  SELECT status, grading->>'correct_choice_id', count(*)
  FROM exercises WHERE type='trace' GROUP BY 1,2;
  -- live  | a | 8      in_review | a | 31   (39/39, zero exceptions)
  ```
  For all 8 live trace rows `grading.correct_choice_id='a'` AND
  `payload.choices[0].id='a'`. Confirmed end-to-end: `GET /v1/session/today`
  returned a trace whose choices render `a,b,c,d` with `a` = the true output.
  A client that always submits `{"choice_id":"a"}` scores 100% on every trace
  exercise without reading a line of code. (predict_the_fix is correctly
  distributed a/b/c/d and spot_the_bug reasons are spread a/b/c — trace-specific.)
- **Root cause (two layers):**
  - `prompts/generator_trace_python_v1.md` — the "Output JSON" template pins choice
    `a` as correct (`misconception: null`) with b/c/d as distractors; the lone
    counter-instruction ("Randomize which id is correct") is textual and the model
    ignores it in favor of the concrete template shape.
  - `pipeline/publish.py:118-133` (`_trace_payload`) copies `candidate.choices`
    verbatim (original id + order) and takes `correct_choice_id` straight from the
    generator, with **no shuffle**. Compare `pipeline/predict_the_fix.py:158-164`
    which does `rng.shuffle(entries)` — exactly why predict_the_fix is unbiased and
    trace is not.
- **Blast radius:** all 8 live traces gameable now; all 31 in_review traces inherit
  the defect on publish. Poisons every trace exercise's solve-rate/percentile,
  trace-concept mastery, and spaced-repetition, because "correct" no longer means
  the user could trace the code. This is the single most important launch blocker.
- **Note on invariant 2:** this is **not** a serializer leak. The serialization
  allowlist (`sessions/service.py:241-248`, `schemas/session.py:40-56`, both
  `extra="forbid"`, drops `misconception`) holds. The leak is upstream in content
  generation. Any fix must add a shuffle in the pipeline and re-key
  `correct_choice_id` — it must NOT touch the serializer, and must not be "fixed"
  by regenerating answers without execution proof.

### C2 — No React error boundary + reveal views dereference unguarded server shapes → full-app white-screen

- **Severity:** Critical (a single malformed grade result blanks the whole SPA mid-session; reload re-hits the same data → persistent outage).
- **Reproduction:** Submit or **skip** an exercise whose `AttemptResponse.reveal`
  is `null` or missing a nested field (`reveal` is typed `Reveal | null`, so `null`
  is contract-legal on a graded/skipped attempt).
- **Root cause:**
  - No boundary anywhere: `frontend/src/main.tsx:10-14` and `App.tsx:68-76` mount the
    tree with no `ErrorBoundary`/`componentDidCatch`; `@sentry/react` is imported but
    `Sentry.ErrorBoundary` is never used.
  - Per-type views dereference without guarding: `components/session/revealViews.tsx:38-45`
    (`reveal.correct_lines.forEach`, `explanation.line_notes.map`), `:63-81`
    (`explanation.trace_table.map`), and `Reveal.tsx:53-54,104-121` cast
    `attempt.reveal as STBReveal/…` and pass straight in. The `skipped` path
    (`Session.tsx:89-92`) routes to the same reveal even though the user expected none.
- **Blast radius:** any render throw unmounts the entire app to a blank `#root`.
  This finding is the amplifier for M9 (partial reveal, bad timezone) — with a
  boundary those become localized error states; without one they are full outages.

---

## HIGH

### H1 — Attempt advisory lock is per-exercise, so cross-exercise first-of-day submits double-write streaks `[verified]`

- **Severity:** High (invariant-5 breach + stat corruption on a normal double-tab/retry).
- **Reproduction:** A user whose `last_active_local_date != today` submits **two
  different** exercises from today's session near-simultaneously (two tabs / retry
  storm).
- **Root cause:** `backend/app/attempts/service.py:443-449` locks on
  `pg_advisory_xact_lock(hashtext(user_id), hashtext(exercise_id:date))`. lock_b
  includes the exercise id, so two *different* exercises take *different* locks and
  do **not** serialize. Both then run `_update_streak_and_attempt_count`
  (`service.py:209-254`): both read `last_active_local_date == yesterday`, both take
  the "extended" branch, both `total_attempts += 1`, both `db.add(StreakEvent(...))`.
- **Blast radius `[verified]`:** `\d streak_events` shows **PK on `id` only, no unique
  constraint** on `(user_id, local_date)`, so two `event='extended'` rows are written
  for one real transition — a direct invariant-5 violation ("every streak transition
  writes *a* row" becomes "one transition writes two"). `total_attempts` also suffers
  a lost update (both read N, both write N+1 → N+1 instead of N+2). The code comment at
  `service.py:429-442` claims the lock stops "a duplicate streak_events row," but it
  only stops the same-exercise race, which `already_attempted` already 409s. Correct
  fix keys the lock on `user_id` (or date-only lock_b) — do not remove the lock.

### H2 — Onboarding gate not enforced on deep-links

- **Severity:** High (flow/auth-integrity; un-provisioned users reach core screens).
- **Reproduction:** As a freshly-authenticated user with `user.onboarded === false`,
  hard-refresh or deep-link straight to `/session`, `/profile`, or `/review`.
- **Root cause:** `App.tsx:13-18` `RequireAuth` checks only auth `status`, never
  `user.onboarded`. Only `RootGate` (`routes/RootGate.tsx:22`) redirects un-onboarded
  users, and it only guards `"/"`. There is also no reverse guard: an already-onboarded
  user can re-open `/onboarding` and silently re-set their `level`.
- **Blast radius:** un-onboarded users reach the session player before ever setting a
  level; `Session.tsx:49` calls `getSessionToday()` for a user with no level pick, and
  behavior downstream (band sampling) is undefined/degraded.

---

## MEDIUM

### M1 — Unhandled 500s bypass the uniform error contract and drop all headers `[verified]`

- **Severity:** Medium (contract violation + lost ops correlation + missing security headers on the error path).
- **Reproduction `[verified]`:** `GET /v1/debug/sentry-test` (mounted because
  `SENTRY_ENVIRONMENT=development`) returns:
  ```
  HTTP/1.1 500 Internal Server Error
  content-type: text/plain; charset=utf-8

  Internal Server Error
  ```
  No `{"error":{...}}` body, no `request_id`, no `X-Content-Type-Options`/CSP/frame
  headers, no `X-RateLimit-*`.
- **Root cause:** `backend/app/main.py` registers handlers only for `ApiError` and
  `RequestValidationError` — there is **no generic `Exception` handler**. An unhandled
  exception propagates to Starlette's default `ServerErrorMiddleware` (plain-text 500,
  outermost), so the custom `security_headers` and `default_rate_limit` middlewares'
  post-processing (`main.py:216-253`) never runs for that response. (Good news: FastAPI
  debug is off, so **no stack trace leaks** — verified.)
- **Blast radius:** a user who hits a real 500 has no `request_id` to give support
  (defeating the `request_id`-in-every-error design), the response isn't machine-parseable
  by the SPA's error handling, and 500 responses ship without the security headers every
  other response carries.

### M2 — Unauthenticated `POST /v1/attempts` is completely unrate-limited `[verified]`

- **Severity:** Medium (a hole in "rate limit everywhere"; low per-request cost but unbounded).
- **Reproduction `[verified]`:** 15× `POST /v1/attempts` with `Authorization: Bearer garbage`
  returned `401 401 … 401` (15/15), never a `429`, no `X-RateLimit-*`.
- **Root cause:** `main.py:139-141` exempts `POST /v1/attempts` from the default
  middleware (delegating to its "self-enforced 10/min per user" limiter), but that
  limiter lives inside `submit_attempt` keyed on `user.id`
  (`attempts/service.py:292-296`) — reached only *after* `require_access_token`
  (`auth/deps.py:40-53`) succeeds. A missing/invalid/expired token is rejected before
  any limiter runs, so unauthenticated requests to this one endpoint hit no ceiling at all.
- **Blast radius:** unbounded 401 flood (each does a cheap HMAC verify); no per-IP brake
  on the highest-value write endpoint. Auth routes have a per-IP limit; this one doesn't.

### M3 — Client-controlled `X-Request-ID` trusted → log injection + correlation spoofing `[verified]`

- **Severity:** Medium (log forging, poisoned correlation, Sentry-tag spoofing).
- **Reproduction `[verified]`:** a request with `X-Request-ID: abc def_fake_field=evil`
  is echoed verbatim in `X-Request-ID` **and** in the JSON error body's `request_id`,
  and (per the log format) into every log line for that request.
- **Root cause:** `main.py:201` sets `request.state.request_id =
  request.headers.get("X-Request-ID") or <generated>`; that value flows into the
  `_RequestIdLogFilter` structured-log field (`main.py:45-62`, format
  `request_id=%(request_id)s`) and `sentry_sdk.set_tag("request_id", …)` (`main.py:207`).
- **Blast radius:** an attacker can inject fake `key=value` pairs into structured logs,
  collide their request id with a victim's to confuse incident triage, or set an
  oversized/misleading Sentry tag. Fix: only accept a server-generated id, or validate
  the header against a strict `req_[a-z0-9]{6,}` pattern before trusting it.

### M4 — Content volume: fresh deterministic content exhausts in days; sampler silently repeats

- **Severity:** Medium (launch readiness / product-trust, not a crash).
- **Analysis:** ~21 deterministic live exercises (7 STB, 8 trace [all gameable per C1],
  ~6 PTF) vs. HANDOFF's 80 target. `build_session_slots`
  (`sessions/sampler.py:155-162`) prefers exercises not in `recently_seen_ids` (14-day
  window) but falls back to `available[0]` when everything is recently seen — so after a
  few days a daily user is re-served exercises they've already answered (the streak/skip
  bookkeeping still fires). Combined with C1, a returning user's trace slots are both
  repeats *and* trivially answerable.
- **Blast radius:** the daily loop feels empty/repetitive within the first week — the
  exact opposite of the retention thesis. This is a "generate more content" item, not a
  gate to weaken.

### M5 — Redis outage 500s the whole authenticated API (fail-closed, no degradation)

- **Severity:** Medium (availability; correct *direction* but no graceful degradation).
- **Root cause:** `core/ratelimit.py:63-72` (`redis.time()` + `redis.eval`, no error
  handling) is called by the `default_rate_limit` middleware (`main.py:229-253`, only a
  `try/finally`, no `except`) and by `submit_attempt`. A Redis `ConnectionError`
  propagates → 500 for every non-exempt route.
- **Blast radius:** a Redis blip takes down everything except `/healthz`, `/v1/auth/*`,
  `/v1/debug/*`. To be clear re the brief's "fail-open?" question: it fails **closed**
  (no unlimited-request bypass), so this is a resilience gap, not a limit bypass.

### M6 — Dashboard/Profile are all-or-nothing on `Promise.all`

- **Severity:** Medium (one degraded analytics endpoint blanks the whole page).
- **Root cause:** `routes/Profile.tsx:210-227` (`Promise.all` of 6 calls, single
  `.catch` → whole-page error at `:244`) and `routes/Dashboard.tsx:30-37` (same across 3).
  A 500 from any one of stats/concepts/activity/accuracy-history/sessions/review discards
  the successful five. Inconsistency: `getReviewStatus` is treated best-effort elsewhere
  (`Profile.tsx:201-208`) yet is a hard dependency in the initial load.

### M7 — OAuth login-CSRF: callback `state` not bound to the initiating browser

- **Severity:** Medium (well-known OAuth gap; partially mitigated by single-use state).
- **Root cause:** `auth/router.py:83-88,112-114` stores `state` only in Redis
  (`oauth:github:state:{state}`, `getdel` single-use) with **no cookie tying it to the
  browser that began the flow**. The documented protection is "single-use state in
  Redis," which prevents replay but not cross-browser fixation.
- **Reproduction:** attacker calls `/v1/auth/github/start`, completes GitHub auth for
  *their* account to obtain a valid `code`+`state`, then induces the victim's browser to
  hit `/v1/auth/github/callback?code=…&state=…`. The victim's browser receives a `rt`
  cookie for the **attacker's** account and silently operates inside it (streak/attempts/
  disputes recorded there; attacker can later inspect). Standard fix: set a signed,
  `HttpOnly` state cookie in `/start` and require it to match in `/callback`.

### M8 — `grading_retry` poison batch stalls all pending summarize grading

- **Severity:** Medium (robustness; reduced because summarize is dropped from the soft launch, but 1 seed summarize is live and the sampler still serves summarize when the grader is healthy).
- **Root cause:** `jobs/grading_retry.py:59-116` has no per-item try/except and a single
  `db.commit()` at the end. It catches only `RubricGradingInvalidResponse`/
  `RubricGradingTimeout` (both bounded — good, no infinite retry there). But any *other*
  exception aborts the batch: `grade_rubric` wraps only the LLM call in its broad `except`
  (`rubric.py:213-223`); the code after — `exercise.grading["rubric"]`,
  `_score_from_response` reading `pass_threshold`/`weight` — is unguarded, so a malformed
  `grading` blob raises a raw `KeyError`. `_run_once` (`jobs/runner.py:80-103`) rolls back
  the session, discarding every grade already resolved in that tick; `_pending_attempts`
  has **no ORDER BY**, so the same poison row is re-fetched and re-aborts every tick.
- **Blast radius:** all `grading_pending` attempts stay permanently ungraded (streak
  already credited at submit, but the user-visible grade, `total_correct`,
  `accuracy_by_type`, and concept mastery never resolve). Bounded-retry aging never
  helps because the poison isn't a `RubricGrading*` exception.

### M9 — Frontend cluster: partial reveal / refresh-failure logout / bad timezone (all amplified by C2)

- **Severity:** Medium (each is a render-time throw or an unwanted eject; C2 turns them into full outages).
- **Root causes:**
  - Review screen trusts reveal sub-shape: `routes/Review.tsx:47-61` guards only
    top-level `row.reveal ?` then casts and the child views deref `.correct_lines`/
    `.explanation.*` (`revealViews.tsx`). A present-but-partial reveal throws during
    `Review.tsx:101` `map`.
  - Background refresh failure hard-logs-out mid-session: `lib/auth-context.tsx:24-38`
    fires 60s before expiry and on `.catch` sets `unauthenticated` → `RequireAuth`
    redirects to `/login`, losing in-progress `selectedLine`/`summaryText`. The
    on-demand 401 refresh in `api.ts:129-135` would have recovered — the proactive
    timer shouldn't hard-eject.
  - Invalid server timezone throws in render: `lib/date.ts:6-9` `new Intl.DateTimeFormat(…,
    {timeZone})` raises `RangeError` on a malformed IANA string; call sites default only
    `null`/`undefined` (`Profile.tsx:198`, `SessionComplete.tsx:35`), and `User.timezone`
    is server-controlled.

---

## LOW

- **L1 — Dispute `attempt_id` unvalidated:** `disputes/service.py:50-57` stores
  `payload.attempt_id` with no check that it belongs to the user or references this
  exercise (it's a D-7 soft link). A user can attach any/nonexistent attempt id.
  Integrity/operator-confusion only; no cross-user data is returned.
- **L2 — Dispute-without-attempt:** `create_dispute` only checks the exercise `(id,version)`
  exists, not that the user attempted it. Any authenticated user can open a dispute on any
  live/existing version (bounded by one-open-per-user-per-version). Spam surface.
- **L3 — Short JWT secret:** live `JWT_SECRET` is 24 chars; `config.py:12` enforces only
  `min_length=1`. HANDOFF already flags these secrets as burned/rotate — rotate to ≥32
  random bytes and add a length floor.
- **L4 — Streak inflation via westward tz changes:** `jobs/streak_recon.py:56-60` clamps
  `last_active_local_date` backward; advancing to the new-tz midnight then re-enters the
  "extended" branch, granting ~+2 streak for one real day. Repeatable, bounded, evades the
  reconcile author's "current_streak never touched" safety because the extension happens on
  the *next* submit.
- **L5 — No request-body size limit:** `AttemptRequest.answer` is `dict[str, Any]`; only the
  key-set/type is validated (`grading.py:46-66`), not value sizes. A multi-MB `reason_id`
  string is accepted and stored in the `attempts` JSONB. DB/memory bloat vector.
- **L6 — A11y:** modals (`DisputeModal.tsx:47-55`, `ReviewPromptModal.tsx:60-72`) set
  `role="dialog"` but no focus trap/initial-focus/restore/scroll-lock; gutter line-select
  (`CodeBlock.tsx:23-41`) makes one tab stop per code line (no roving tabindex).
- **L7 — Idempotency key lifetime / tally double-count:** `lib/idempotency.ts:4` keys per
  `exercise_id` for the module lifetime (not "per serve" as commented); and two clicks that
  both dispatch before `setPhase('submitting')` commit run `applyGraded` twice
  (`Session.tsx:86-91`), inflating the local correct/total tally (backend stays idempotent).
- **L8 — Latent `misconception` in payload:** `pipeline/publish.py:124` writes `misconception`
  (null on the correct choice) into `payload.choices` in the DB. Not leaked today (session
  allowlist strips it) but any future wholesale `payload.choices` dump would reveal the answer
  directly — an even more direct leak than C1.
- **L9 — D-90 fallout:** 5 `in_review` llm STB have `grading.artifacts.fixed_code_hash` but no
  `fixed_code`; they grade/reveal fine (STB reveal needs neither) but can never be derived into
  predict_the_fix. No live impact. Unrecoverable (hash is non-invertible), as D-90 records.
- **L10 — `hashtext` lock collisions:** `attempts/service.py:444` — two distinct `(user,exercise:date)`
  triples can collide onto the same int4 lock pair, over-serializing unrelated submits.
  Correctness-safe (a given triple always self-collides, so real duplicates always share a lock),
  throughput-only.

---

## Verified robust (attacked, no finding)

These were probed and held up; recording them so the report is not read as "all broken."

- **JWT verification** (`auth/tokens.py:79-118`): exact header match `{"alg":"HS256","typ":"JWT"}`
  blocks `alg:none`/alg-confusion; exact claim-set match; constant-time `hmac.compare_digest`;
  expiry enforced. No forgery path found.
- **IDOR** `[verified]`: `GET /v1/attempts/{id}` is scoped by `user_id`
  (`attempts/service.py:612-615`) — user 213c reading another user's attempt #2 returned **404**.
  Every `/v1/me/*` and `/v1/session/*` route derives the user from the JWT and queries by
  `current_user.id`; no route takes a caller-supplied user id.
- **Invariant 2 (answer-key leak) at the serializer** `[verified]`: `_serialize_payload`
  (`sessions/service.py:229-262`) is a field-by-field allowlist over `extra="forbid"` schemas
  (`schemas/session.py`), drops trace `misconception`, and never copies `grading`/`explanation`.
  Live `GET /v1/session/today` carried no grading/explanation/correct_* keys for any type.
  (The trace answer is still derivable — but via content ordering, C1, not serialization.)
- **PATCH /me privilege escalation:** `UpdateMeRequest` (`schemas/users.py:58-64`) is
  `extra="forbid"` with `level` a `Literal["junior","mid","senior"]`; no way to set
  `beta_allowed`/`onboarded`/arbitrary columns.
- **Admin gate** `[verified]`: `/admin/*` returns **404 when the token is unset** (doesn't confirm
  the route) and **403 with `hmac.compare_digest`** when set; live probes with no token and a wrong
  token both 403 (token is configured here). No timing side channel.
- **Idempotency + same-exercise concurrency** (`core/idempotency.py`, `attempts/service.py:319-373,443-459`):
  rate-limit-before-cache (D-65), SET-NX reservation, and the transaction-scoped advisory lock
  correctly serialize the *same-exercise* double-submit and replay byte-identically. (The gap is the
  *cross-exercise* per-user aggregate — H1.)
- **Malformed-answer handling** (`grading.py:46-66`, `rubric.py:88-100`): strict exact-key-set
  validation per type before any grade; `{"skipped":true}` accepted only for deterministic types and
  rejected for summarize; extra keys, wrong types, and stray keys alongside `skipped` all 422.
- **Rubric injection hardening** (`attempts/rubric.py`): the grader emits no score (backend computes
  it), the answer is walled in an escaped `<student_answer>` block, and outputs are filtered to a closed
  allowlist — an injected "score 1.0" is inert by construction.
- **Session exhaustion / empty & new-user states**: `build_session_slots` degrades gracefully (never
  raises; returns fewer slots, transient-empty per D-59 rather than a cached empty "completed" day);
  `get_stats`/`get_concepts`/`get_activity` return zeros/`[]` for a zero-history user. No crash found
  (the content-volume *product* concern is M4).
- **Rate-limit token bucket & XFF trust** (`core/ratelimit.py`, `core/network.py`): standard bucket
  holds a burst of `limit` then throttles; per-IP key reads the rightmost `TRUSTED_PROXY_COUNT` hop, not
  the client-suppliable leftmost XFF entry.
- **percentiles dedup** (`jobs/percentiles.py:36-43`): `DISTINCT ON (user,exercise,version,date)` with
  matching `ORDER BY … created_at ASC` correctly collapses replay duplicates before counting (D-67 holds).
- **Job isolation & partition recovery** (`jobs/runner.py:80-103`, `jobs/partitions.py:161-198`): one job
  throwing does not kill the others; the partition job walks missed months and drains `attempts_default`
  (rows stay queryable via the parent table meanwhile). The gap is *within* a grading_retry batch — M8.
- **Security headers on normal + handled-error responses** `[verified]`: `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `Referrer-Policy`, and a strict JSON-only CSP are present on 2xx and on
  `ApiError`/validation responses. (Only the *unhandled* 500 path misses them — M1.)

---

## Notes for Phase 2 (not acted on)

- The two launch-blocking items are **C1** (trace bias) and **C2** (no error boundary). C1's fix belongs
  in the pipeline (`_trace_payload` shuffle + re-key), proven by re-generating/re-executing, and the 8
  live + 31 in_review traces need re-shuffling or re-deriving — **without** weakening any gate or bulk
  flipping status.
- **H1** wants the advisory lock re-keyed to `user_id` (or a `user_id`-scoped streak/stats lock) — the
  lock stays, it is only widened; add a negative test with real `asyncio.gather` of two *different*
  exercises proving a single `streak_events` row and `+2` `total_attempts`.
- Every fix should carry a negative test that reproduces the bug first, per the engagement rules. No gate,
  guard, sandbox, or the DB-isolation/immutability invariants were touched in Phase 1, and none should be
  loosened to make any of these findings go away.
