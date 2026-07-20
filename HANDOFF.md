# CodeReader — Handoff Brief

Paste this into a new chat to resume. Everything else lives in the repo
(`CLAUDE.md`, `docs/00`–`docs/09`, `docs/07-decisions.md` = D-1..D-122).
Forward plan (what to build next) lives in `docs/10-roadmap-retention.md`.

Last refreshed: 2026-07-18 (A1 and A2 both merged to master; D-116..D-122).

---

## What this is

**CodeReader** — "Duolingo for reading code." Daily 5–10 min sessions where devs
read code they didn't write and spot bugs, trace output, or predict the fix.
Pitch: AI writes code now; the scarce skill is *verifying* it.

**The core trust promise:** no exercise ships unless its answer was proven by
execution. That's the whole product.

Stack: FastAPI + Postgres 16 + Redis, React 18/Vite/TS/Tailwind, a content
pipeline with a Docker sandbox and adversarial LLM gates. Repo:
`D:\projects\codereader`. Windows host; local dev runs via Docker Compose.

**Deployed (soft launch live):**
- Backend: FastAPI Cloud, `https://codereader.fastapicloud.dev`
- Frontend: Vercel, `https://codereader-eight.vercel.app`
- DB: Neon Postgres (free tier). Frontend proxies `/v1/*` to the backend via a
  Vercel rewrite so the API is same-origin (D-114); this is what makes the OAuth
  refresh cookie work. Deploy gotchas are in `docs/09`.

---

## Status: MVP built, deployed, and in soft launch

**Production and `master` are NOT the same thing right now.** LIVE IN
PRODUCTION: the MVP only (M0-M8, soft launch). ON `master`, MERGED AND
UNRELEASED: the whole retention layer so far, A1 (streak safety net) and A2
(email capture), plus D-119/D-121/D-122. Nothing below describing A1 or A2 is
running in production yet.

All milestones M0-M8 complete and the app is live end to end in production:
GitHub OAuth login, onboarding, daily session, instant deterministic grading,
streaks, spaced repetition, stats, disputes. The session gate was removed so
reaching `/session` opens the player directly (D-111). Frontend passed a full
Playwright session smoke test and scored 0/16 on the anti-slop audit across every
screen; the Review/Dashboard/Profile screens got a dual-pane + glassmorphism
polish pass (see `docs/ops-incident-report-july-2026.md`). 517 backend tests green
(456 predated A1; A1 took it to 457, A2 added 49, D-121/D-122 added 8, D-119's
close added 3). The Playwright suite is 14 passed / 0 skipped: the last
test.fixme was removed when D-119 closed.

**Retention layer: A1 and A2 are BUILT and MERGED TO MASTER. A3 is next.**

A1 (streak safety net) added freeze accrual and consumption, repair / earn-back,
an ops outage freeze, and a "welcome back" state in place of guilt copy. The
load-bearing decision is D-116: a "covered day" is read from the `streak_events`
ledger, not inferred from the freeze balance, so an outage fills a day for
everyone without spending anyone's balance. New routes: `POST /v1/streak/repair`
(idempotent, advisory-locked) and two admin ops routes
(`/admin/streak/outage-freeze`, `/admin/streak/grant-initial-freezes`).
`/v1/me/stats` gained `repair_available` and `repair_restores_to`. Also D-117
(both `.env.example` files are drift-checked now; the root one had already
drifted) and D-118 (one-time backfill of the starting freeze balance for pre-A1
accounts, run once after deploy).

A2 (email capture) added in-app email capture with verification, so A3 has a
notification channel. GitHub OAuth stays scoped `read:user`. D-120 covers it:
capture in-app rather than widening the scope (widening would force re-consent
on every existing user); a new address waits in `pending_email` so a typo cannot
take a working address offline; uniqueness is a PARTIAL index (verified and not
soft-deleted) so an address cannot be squatted by typing it; tokens are hashed,
single-use and expiring, matching refresh-token storage; every verification
failure returns ONE generic response so nothing is an enumeration oracle. New
routes: `POST /v1/me/email`, `POST /v1/me/email/verify`,
`POST /v1/me/email/resend`, `DELETE /v1/me/email`. `GET /me` gained `email`,
`email_verified` and `pending_email`. **Migration 0009** adds `users.email` /
`email_verified_at` / `pending_email` plus `email_verification_tokens`; no
backfill needed. This is the first migration in the retention work, so A2's
release is NOT the no-migration shape A1's was.

**A3 (reminders + weekly recap) IS BUILT, on branch `a3-reminders-recap`
(D-137). It is NOT deployed and NOT merged.** Migration **0010** adds
`email_deliveries` (the send-once ledger) and `email_suppressions` (permanent,
per-user opt-out). New routes: `PATCH /v1/me/email-prefs`, and the two PUBLIC
unsubscribe routes `POST /v1/unsubscribe?token=` (RFC 8058 one-click, no login)
and `GET /v1/unsubscribe/preview?token=`. `GET /me` and `/auth/refresh` gained
`reminder_local_time` (promised by docs/05 since M6 but never actually in the
allowlist) and `email_prefs`. Two new jobs run off the existing `jobs/runner.py`.
Frontend: a reminders card on Profile and a public `/unsubscribe` page.

The load-bearing decision is the send-once mechanism: an `email_deliveries`
LEDGER whose PRIMARY KEY `(user_id, kind, period_key)` IS the ceiling, claimed
and COMMITTED before the provider call, with a deterministic Resend
`Idempotency-Key` as a second layer. `claimed` is terminal on purpose, because a
duplicate reminder costs more than a missed one. This is D-116's argument one
layer up: a recorded fact, never a recomputation that a timezone change can move.

**THE HARD PREREQUISITE IS STILL OPEN, and building A3 did not close it.**
Resend will only send from a verified domain, needing SPF, DKIM, MX and DMARC
records. `EMAIL_FROM` still points at `no-reply@codereader.dev`, **a placeholder
nobody owns**, and neither `codereader-eight.vercel.app` nor
`codereader.fastapicloud.dev` can be used (you cannot add DNS records to a
domain you do not control). D-114 deferred buying a domain; A3 cannot SEND until
that is reversed, and DNS propagation plus verification is a lead-time item.
So "paste a real `RESEND_API_KEY` and flip `EMAIL_SENDING_ENABLED=true`" is
NECESSARY AND NOT SUFFICIENT: with the key set but no verified domain, every
send returns a provider error, which the job records as `failed` and retries to
its cap. `APP_ORIGIN` should move at the same time, since verification AND
unsubscribe links are built from it, and a domain change touches D-114's
same-origin rewrite and the `GITHUB_REDIRECT_URI` rule in docs/09 section 3.
`EMAIL_SENDING_ENABLED` defaults false, so nothing sends until deliberately
enabled.

**A3 GO-LIVE ENV, and the job-runner half is the easiest thing to forget.** A
correct reminder system that never ticks is the most likely way this fails
silently: no error, no mail, nothing in Sentry, and the ledger simply stays
empty. The A3 release checklist is therefore:

| Setting | Value | Where |
|---|---|---|
| `JOBS_ENABLED` | `true` (already the default, and already `true` in both `.env.example`) | FastAPI Cloud |
| `JOB_REMINDERS_INTERVAL_S` | `60` for launch, NOT the 300 code default (both `.env.example` now say 60) | FastAPI Cloud |
| `JOB_WEEKLY_RECAP_INTERVAL_S` | `900` (default is fine) | FastAPI Cloud |
| `RESEND_API_KEY` | the real key | FastAPI Cloud |
| `EMAIL_SENDING_ENABLED` | `true` | FastAPI Cloud |
| `EMAIL_FROM` | `Reedkode <no-reply@reedkode.com>` once the domain is verified | FastAPI Cloud |
| `APP_ORIGIN` | the production frontend origin | FastAPI Cloud |

**Why the interval must come down from 300.** The reminder job is a SWEEP, not
a scheduler: it fires for everyone whose local time is at or past their chosen
minute, so the tick interval IS the worst-case lateness. At the 300s default a
user who picked 08:00 can be mailed at 08:04:59. At 60s the worst case is 59
seconds, which is "near their chosen minute" in any sense a user would notice.
The interval cannot be lowered indefinitely: each tick is a query plus up to
`EMAIL_MAX_SENDS_PER_TICK` paced sends, so 60s is the floor at which a tick
still finishes before the next one starts at launch volume. It is NOT an
hour-late system by default -- 300s is five minutes, not sixty -- but 60s is
the right launch value.

**Does the runner actually start on FastAPI Cloud?** Yes, and the mechanism is
worth naming because it is the load-bearing assumption. The scheduler is
started from the FastAPI **lifespan** (`main.py`), not from a cron container
and not from a separate worker process, so it runs wherever the ASGI app runs.
Two consequences: (a) if FastAPI Cloud ever scales to more than one instance,
EVERY instance runs the jobs -- which is safe, because the `email_deliveries`
primary key means only one instance can claim any period, but it does multiply
the harmless no-op queries; (b) if the platform idles the app to zero when
there is no traffic, the jobs stop with it. **Verify after deploy** with
`GET /admin/metrics`, which reports `run_count` and `last_run_at` per job:
**`reminders.run_count` climbing in `/admin/metrics` is the ONLY proof the
layer is alive.** Nothing else distinguishes "no reminders were due" from "the
job has not run since the last deploy": both look like an empty
`email_deliveries` table and a silent inbox. A `run_count` that stops climbing
between two polls is exactly the failure this metric exists to catch, and on a
scale-to-zero platform it is the expected failure (D-138) rather than an
exotic one. Check it after every deploy.

**THE EXTERNAL TRIGGER IS PART OF GO-LIVE, NOT AN OPTIONAL EXTRA (D-138).**
FastAPI Cloud scales to zero, and the in-process scheduler dies with the app.
Worse, each job loop counts its interval from PROCESS START, so a cold start
resets the clock and an app that wakes briefly and sleeps again never reaches a
tick at all. Without the trigger, reminders simply do not send overnight, which
is when they are due. Steps:

1. Add two **GitHub repo secrets**: `API_BASE_URL` (the backend origin, e.g.
   `https://api.reedkode.com`) and `ADMIN_METRICS_TOKEN` (the same value set on
   FastAPI Cloud).
2. Set `ADMIN_METRICS_TOKEN` on **FastAPI Cloud**. While it is empty the
   endpoint is 404, so an unconfigured deploy cannot be made to send.
3. `.github/workflows/jobs.yml` runs every 10 minutes on the default branch.
   It only runs from the DEFAULT BRANCH, so it does nothing until this is
   merged and pushed.
4. Trigger it once by hand (`workflow_dispatch`) and confirm a 200 whose body
   shows real sweep counters, then confirm `reminders.run_count` moved in
   `/admin/metrics`.
5. **Calendar reminder: in a public repo GitHub disables scheduled workflows
   after 60 days with no repository activity.** A quiet repo silently stops
   sending reminders. This is the single most likely way this layer dies later.

The in-process scheduler is left enabled and unchanged, so local dev needs none
of this and an always-on host would work without the trigger.

**LAUNCH BLOCKER 2, alongside the domain: the Resend plan.** The free tier is
**100 emails/day and 3,000/month**, and a public launch clears that almost
immediately. Volume is deterministic, because A3 sends at most one reminder per
user per day and one recap per user per week:

| Subscribed users | Reminders/day | Recap day adds | Peak day (Monday) | Per month |
|---|---|---|---|---|
| 200 | up to 200 | +200 | **400** | ~6,800 |
| 500 | up to 500 | +500 | **1,000** | ~17,000 |
| 1,000 | up to 1,000 | +1,000 | **2,000** | ~34,000 |

Those are ceilings, not forecasts: a reminder is skipped for anyone who already
practised that day, and an empty week is skipped entirely, so real volume is
lower and falls as engagement rises. Even so, **200 subscribed users exceed the
free daily cap on any Monday, and ~90 users exceed it on an ordinary day.**

Pricing: **Pro is $20/mo for 50,000 emails**, then $35/mo for 100,000; Scale
starts at $90/mo for 100,000. Overage on Pro is $0.90 per 1,000. So the entry
Pro plan covers 1,000 fully-subscribed users (~34,000/mo) with room to spare,
and the decision at launch is simply free-to-Pro, a $20/mo line item. Free also
allows only ONE verified domain, which is enough for reedkode.com but leaves no
room for a separate staging sender.

**Does the job degrade gracefully or hammer the limit?** It degrades, and this
was designed rather than lucky, but the two limits fail differently:
- **The per-second rate limit is respected by construction.** Sends are
  sequential and paced at `EMAIL_SENDS_PER_SECOND` (2/s, against a documented
  ceiling of 10/s per team), never a concurrent fan-out, and
  `EMAIL_MAX_SENDS_PER_TICK` caps each tick. It cannot burst.
- **The daily/monthly cap is NOT respected, because the job cannot see it.**
  Once the plan quota is exhausted Resend starts refusing, and every refusal is
  an `EmailSendError` that lands the period in `failed` with an attempt count.
  That is graceful in the sense that matters -- it does not crash the job, does
  not mark the period sent, does not double-send, and stops after
  `EMAIL_SEND_MAX_ATTEMPTS` -- but it is NOT self-limiting: it will keep
  re-attempting up to the cap for every user, every tick, and the visible
  symptom is a pile of `failed` rows rather than an alert. **Watch for
  `email_deliveries` rows with `status='failed'` after launch; that is the
  quota signal.** Staying on the free tier past ~90 users therefore produces
  mail that silently stops for most users while the job looks busy.

**Three fixes rode in on the A2 branch, unrelated to email** (deliberately not
split out; see the A2 merge commit):
- **D-122**: first-of-day session creation is serialized by a per-(user, day)
  advisory lock (D-104's lock class, third application). Two concurrent
  `GET /v1/session/today` both inserted `daily_sessions`; the loser hit the PK
  and the IntegrityError recovery then failed on its own re-read, returning 500.
  The MissingGreenlet that recovery raised is UNEXPLAINED and deliberately
  unfixed: the lock makes it unreachable, and that branch firing again is
  evidence the lock was bypassed, not a licence to catch the symptom.
- **D-121**: an unhandled exception now reaches the browser AS a 500, with a
  JSON body and CORS headers. It was generated outside `CORSMiddleware`, so the
  browser saw a rejected fetch and the SPA said "Could not reach the server".
  That disguise cost two misdiagnoses.
- **D-119**: CLOSED. `session.spec.ts` asserted a "Session complete" screen that
  does not exist, so it failed 8 of 8 on a confusing selector. Fixed to assert
  the real completion signal. No `test.fixme` remains in the Playwright suite.

**Both A1 and A2 are merged to master but NOT DEPLOYED**, and merging ships
nothing: Vercel is CLI-only and the backend deploys separately. Branches
`a1-streak-safety-net` and `a2-email-capture` are retained, not deleted, and
master is 25 commits ahead of `origin/master` and unpushed. The A1 release
checklist is in `docs/09` section 5 (backend before frontend, no migration, no
new required env, one post-deploy backfill call); A2 adds migration 0009 and the
`EMAIL_*` env knobs to that list.

Deferred out of A1, deliberately: there is **no session-complete screen**.
`Session.tsx` redirects to the Dashboard when the last exercise is done, so A1's
"dashboard and session-complete" requirement is met on the Dashboard and in the
per-attempt reveal only. Building that screen is its own piece of work.
This absence bit once already (D-119): `session.spec.ts` asserted a "Session
complete" screen and failed 8 of 8 on a confusing selector for it. Anything
asserting end-of-session must target the Dashboard redirect and its completed
state until that screen actually exists.

Three exercise types, **all deterministically graded (zero per-answer LLM cost)**:
- `spot_the_bug` — tap the buggy line + pick why (the flagship)
- `trace` — what does this print
- `predict_the_fix` — which fix makes the failing test pass (derived from STB
  survivors; every distractor is *executed* and must still fail the test)

`summarize` was built (M5, with real prompt-injection hardening) but **dropped
from the soft launch** — it's the only type with a per-answer LLM cost.

---

## Resolved since the last handoff (kept for history)

- ✅ **pytest DB-wipe guard (D-88).** `conftest.py` now calls
  `assert_disposable_test_database()` and refuses to run unless the target DB is
  an explicit `_test` database. The "every test run destroys content" footgun is
  closed.
- ✅ **Content restored and grown.** The corpus is now ~109 exercises in
  production (D-110 review pass reviewed 77, killed 4). No longer 6 rows.
- ⚠️ **Secrets:** prod uses its own cryptographic keys, separate from the dummy
  local `.env` values (incident report §3). VERIFY the July-12 burned OpenAI /
  GitHub keys were actually rotated at the provider, not just left unused.

## Known production issues (low severity, understood)

From `docs/ops-incident-report-july-2026.md`:
- **Profile "Couldn't load..."** = token-refresh race: the page fires 5 concurrent
  calls; on an expired token + a Neon free-tier pool timeout they can all 401 at
  once. Handled gracefully section-by-section (`usePanel`); a reload fixes it.
  Real fix is upgrading the Neon tier for more pooled connections.
- **"Something went wrong" mid-session**: the stated cause was WRONG and is
  corrected in D-121. It is NOT "the 403 `exercise_not_in_session` lacks an
  `{error: ...}` body": that 403 is raised as `ApiError`, has always carried the
  standard body, and the M4 test
  `test_attempt_on_exercise_not_in_session_returns_403` has asserted exactly
  that body since M4. The leading
  hypothesis is now the D-121 CORS gap: an unhandled 500 reached the browser
  with no CORS headers, so the SPA saw a rejected fetch instead of a readable
  500. `POST /v1/attempts` calls `get_today_slots()`, which is the same function
  that was 500ing under the D-122 race, so the two incidents plausibly share one
  cause. FIXED at the contract level (D-121); the specific incident is not
  confirmed closed because it was never reproduced.

---

## Current content state

~109 exercises in production across `spot_the_bug`, `trace`, and
`predict_the_fix` (all Python). D-110 was the first full human-review gate run
(77 reviewed, 4 killed). For the live breakdown, always query rather than trust
this doc:

```powershell
docker compose exec postgres psql -U codereader -d codereader -c "SELECT source->>'origin' AS origin, type, status, count(*) FROM exercises GROUP BY 1,2,3 ORDER BY 1,2;"
```

Human review via `review_cli packet` is the last gate before `live`. Do not bulk
-flip to live.

---

## The pipeline saga (read this before touching the pipeline)

The pipeline generates → static gate → **Docker sandbox (real execution)** →
semantic gates (defect_audit / solver / reasons) → dedup → publish `in_review`.

**Five structural bugs were found, all of which looked like "the model is too
weak" but weren't.** The pattern repeated so often it's worth internalizing:

1. **D-45** — sandbox check 5 used a *positional* index-zip diff, so any fix that
   inserted a line cascaded and was rejected **by construction**. Fixed with
   `difflib.SequenceMatcher`.
2. **D-46** — a generator prompt constraint told the model to pre-plant forbidden
   scaffolding (`import threading`) that the static gate then rejected. The prompt
   was fighting the gate.
3. **D-57 (the big one)** — **the sandbox never executed a single candidate.** The
   runner bind-mounted a temp file path that the host Docker daemon couldn't see
   (the pipeline runs *inside* a container), so Docker silently created an empty
   *directory* and Python reported "can't find `__main__`". Every sandbox rejection
   ever, across every model, was this. Fixed by piping source via **stdin** and
   adding a **canary self-check** that fails loudly if the sandbox isn't executing.
4. **D-54 / D-80** — some taxonomy concepts are **un-generatable for spot_the_bug by
   construction**: "omission bugs" (fix is a pure insertion → no line to point at)
   and "no-divergence bugs" (buggy and fixed produce identical output → no test can
   discriminate). Flagged unsamplable.
5. **D-81** — `defect_audit` was a **broken judge**: gpt-4o-mini found the correct
   bug but reported the *wrong line number* (it was counting lines in un-numbered
   code, undercounting more with depth), and an exact line-set match killed the
   candidate. ~11 of 14 semantic rejects were **false**. Fixed by feeding
   line-numbered code, tolerant ±2 matching, and upgrading `GATE_MODEL` to `gpt-4o`.

**Lesson: a ~100% failure rate is the signature of a structural rejector, not a
model ceiling.** A genuine capability limit produces a *distribution*. Four
separate times, escalating the model was the wrong lever.

### The one real model ceiling

`buggy_fails_test` — the model plants a real bug, then picks a test input where
buggy and fixed produce *identical* output, so the assertion never fires. Three
independent, well-targeted fixes all failed to move it:
- a worked example (v3)
- full SymPrompt-style decomposition with forced divergence fields (v4)
- **targeted feedback repair with the exact failure evidence: 0 successes out of 12**

Choosing a divergence-boundary test input is the core cognitive act of authoring a
spot_the_bug, and gpt-4.1 cannot do it. This is why exercises are now being
hand-authored.

### What works well

- **Feedback repair** (D-83): rescues `captured_output_matches_claim` (trace
  mis-traces) at 10/15. Rescues `buggy_fails_test` at **0/12**. Repair is cheaper
  than regeneration ($0.064/rescued vs $0.096/published).
- **Prompt caching** (D-86): 61% cache hit, saved $0.35/batch.
- **Free static check (B3, D-82)**: if the model's own claimed buggy result equals
  its claimed fixed result, reject at schema validation — zero tokens, zero
  sandbox.
- **Coverage-weighted sampling**: `1/(1+live_count)`, steers toward zero-coverage
  concepts.
- Cost: **~$0.06–0.10 per published exercise.** 80 exercises ≈ $5–8.

Models: `GENERATOR_MODEL=gpt-4.1`, `GATE_MODEL=gpt-4o` (must differ — **D-14**: a
model must never grade its own output). **OpenAI only**; no Anthropic key.
`GENERATOR_MODEL_STB=gpt-5.5` routing exists but is **OFF** (5–15x cost, doesn't
fix structural bugs).

---

## Hand-authored exercises (the current approach)

Claude writes STB exercises directly; they go through the **full, unmodified gate
chain** via `python -m pipeline.ingest --file <path>` (D-87). Nothing is trusted
because a human wrote it.

**D-14 still binds:** since Claude authors them, the semantic gates MUST run on
the OpenAI path (`GATE_PROVIDER=openai`, `GATE_MODEL=gpt-4o`). Claude must never
solve/audit/judge its own exercises.

**Batch 1 result: 5 of 7 published.** Two legitimate rejections:
- `aliasing-vs-copy` — a distractor was *accidentally true* (integer division
  really does truncate), flagged `partially_defensible` (D-13).
- `generator-exhaustion` — the solver correctly identified the mechanism but named
  the line where the *symptom* appeared, not the root cause. The exercise had two
  defensible "buggy lines." Genuinely ambiguous; deserved to die.

**Authoring rules learned:** exactly ONE unambiguous buggy line; distractors must
be *cleanly false*, not "true but less relevant."

### Zero-coverage STB concepts still needed

`context-manager-misuse`, `dict-mutation-during-iteration`, `exception-swallowing`,
`variable-shadowing`, `string-vs-bytes-confusion`, `key-function-misuse`,
`float-precision`, `boolean-short-circuit-side-effect`, `shared-class-attribute`,
`string-immutability-misuse`, `memoization-cache-staleness`, `off-by-one-slicing`,
`sorting-stability-assumption`, `injection-string-concat`,
`string-formatting-mismatch`, `dataclass-mutable-default`, `walrus-scope`,
`global-state-mutation`, `list-mutation-during-iteration`, `truthy-falsy-empty-check`,
`recursion-missing-base-case`, `encoding-decoding-mismatch`, `timezone-naive-vs-aware`,
`is-vs-equality`

### Sandbox invariants an authored STB must satisfy

1. `buggy_code + test_code` → **non-zero exit AND `AssertionError` in stderr**
2. `fixed_code + test_code` → exit 0
3. `buggy_code` alone → exit 0 (no crash on the happy path)
4. deterministic across a double run
5. `diff(buggy, fixed)` **modifies at least one existing line** (a pure insertion
   is rejected — there's no line to point at)
6. the test **`print(repr(result))` before asserting**, and the claimed
   `buggy_result_on_divergence_input` / `fixed_result_on_divergence_input` must
   match real execution byte-for-byte (B4 / D-82)
7. no forbidden imports (`random`, `time`, `os`, `io`, `threading`, `asyncio`,
   `subprocess`, `uuid`, network, sets), no hint words in code/comments
   (`bug`, `fix`, `wrong`, `careful`, `note`)

---

## Known open items

**Seeded Playwright specs are flaky again (D-136, OPEN).** Three different
specs each failed once across ~5 runs on :5173, never twice, never together,
always passing in isolation: `session.spec.ts`, `scroll-reachability.spec.ts`,
and (hermetic, so the best lead) `viewer-narrow.spec.ts` when grouped with
`narrow-two-state.spec.ts`. Do NOT file this under D-122, which is closed on
15/15 evidence; if it is the same race, that fix regressed and needs saying so.
Undiagnosed. Note that runs against a harness server on :5174 fail two seeded
specs DETERMINISTICALLY for an unrelated reason (APP_ORIGIN pins CORS to
:5173) -- that is configuration, not flakiness, and the two must not be
conflated.


**Pre-launch (from the Fable/Opus whole-system audit):**
- ✅ job runner wired, exercise pull path, transient empty sessions, seed gating,
  difficulty bands (D-58..D-62)
- ✅ Sentry (D-63), rate limits, concurrency locks, streak reconciliation,
  partition recovery, security headers, backup/restore drill (D-64..D-73)
- ✅ **conftest DB wipe** guarded (D-88)
- ⚠️ **rotate secrets** — verify the burned July-12 keys were rotated at provider
- ⚠️ `/admin/metrics` uses a shared-secret token, not real auth. This was
  accepted on the grounds that the population would be a 20 to 30 person beta,
  and THAT GROUND NO LONGER HOLDS now the plan is a full public launch. An empty
  `ADMIN_METRICS_TOKEN` disables the endpoint (404), which is the safe default;
  anything else needs a deliberate decision.
- ⚠️ alert catalog is **log-only** — nothing actually pages anyone
- ⚠️ CI dependency-audit job has never run against live advisory feeds

**Polish (deferred, agreed):**
- "1 days" pluralization
- streak should render as **gutter ticks**, not a single dot (docs/08 intent)
- **the profile + session-complete screens are sparse and underdesigned** — the
  session player is strong, the surrounding screens need a design pass. Own
  milestone, after content exists.

**Then:** human-review the corpus via `review_cli packet` and flip to live.
**This is a FULL PUBLIC LAUNCH, not a 20 to 30 person invite beta.** The earlier
plan here was to invite 20 to 30 devs and gate on a D1/D7 retention read; that
plan is withdrawn. D1/D7 from a couple of dozen hand-picked invitees was never
going to be a usable signal (the sample is too small and too friendly to
separate a real retention curve from noise), and the retention layer in docs/10
is built on the research rather than on that read. Signup is open:
`BETA_GATE_ENABLED` already defaults false per D-92.

**Do NOT flip `BETA_GATE_ENABLED` or unwire the gate.** Per D-92 it is a switch,
not a wall, and `beta_allowed` / `beta_invites` / `_apply_beta_invite` stay wired
and populated on every login. It is the reserve control for abuse, cost, or a
content incident, and deleting it is exactly what D-92 declined to do.

Readiness criterion, unchanged in substance and no longer called a beta
criterion: a week of daily sessions with **zero manual intervention**.

Two things a public launch makes load-bearing that a 20 to 30 person beta did
not:
- `/admin/metrics` shared-secret auth was accepted BECAUSE the population was
  20 to 30 known people (see the item above). That justification is gone. It is
  not a launch blocker on its own, since the endpoint is disabled entirely when
  `ADMIN_METRICS_TOKEN` is empty, but it must be either left disabled in
  production or given real auth, deliberately rather than by default.
- The volume assumptions in A3's batching (D-137(10)) were sized at 1,000
  users. A public launch is the scenario that reaches them, and the Resend free
  tier (100/day, 3,000/month) is the first thing that breaks.

---

## Ops gotcha: killing a process by port on Windows

**Do not free a port by killing whatever is listening on it.** On Windows,
Docker Desktop holds a listener on published container ports ALONGSIDE the
WSL relay, so a port-based kill can match `com.docker.backend` and take the
whole Docker engine down with it -- every container stops, and the API
disappears while you are still looking at the frontend.

This happened while freeing 5173 for a fresh vite: `Get-NetTCPConnection
-LocalPort 5173 | Stop-Process` matched both `wslrelay` AND
`com.docker.backend`. Recovery is `Start-Process "C:\Program
Files\Docker\Docker\Docker Desktop.exe"`, wait for the engine, then
`docker compose up -d` -- containers restart rather than being recreated, so
no data is lost, but it is several minutes of confusion.

Kill by process identity instead, e.g. match the `node`/`vite` process, or
stop the dev server in the terminal that owns it.

## Commands

**Production:** frontend `https://codereader-eight.vercel.app`, backend
`https://codereader.fastapicloud.dev`, DB on Neon. Backend redeploy:
`fastapi cloud deploy backend` with the App Root Directory set to `.` (see
`docs/09` for the directory / wheel / OAuth-cookie gotchas). The commands below
are for LOCAL development.

**Start (local):**
```powershell
docker compose up -d postgres redis api
docker compose exec api alembic upgrade head
docker run --rm -d --name frontend-dev -p 5173:5173 -v D:\projects\codereader\frontend:/app -w /app node:20 npx vite --host 0.0.0.0 --port 5173
```
App: http://localhost:5173

**Stop:** `docker stop frontend-dev; docker compose stop`
(**never** `docker compose down -v` — it destroys the volume)

**Generate content:**
```powershell
docker run --rm --network codereader_codereader `
  -v D:\projects\codereader:/work -w /work `
  -v //var/run/docker.sock:/var/run/docker.sock `
  -e DATABASE_URL="postgresql://codereader:codereader@postgres:5432/codereader" `
  -e OPENAI_API_KEY="<key>" `
  -e GENERATOR_PROVIDER="openai" -e GATE_PROVIDER="openai" `
  -e GENERATOR_MODEL="gpt-4.1" -e GATE_MODEL="gpt-4o" `
  -e ANTHROPIC_API_KEY="unused" -e SANDBOX_HOST="" `
  python:3.12 sh -c "apt-get update -qq && apt-get install -y -qq docker.io >/dev/null 2>&1 && pip install -q -e backend && python -m pipeline.orchestrator --n 35"
```

**Review packet:** `python -m pipeline.review_cli packet --out pipeline/review_packet.md --limit 500`

**Back up (do this before EVERY batch):** `backend/scripts/backup_db.sh`

**Content state:**
```powershell
docker compose exec postgres psql -U codereader -d codereader -c "SELECT source->>'origin' AS origin, type, status, count(*) FROM exercises GROUP BY 1,2,3 ORDER BY 1,2;"
```

---

## Working style that's been productive

- Claude writes detailed prompts → an agent (Claude Code) executes → the report
  comes back → Claude reviews it critically.
- **Every milestone is proven by execution, never by assertion.** Named tests,
  real output, real timestamps.
- **Negative tests are the spine.** A gate that can't prove it *rejects* a crafted
  bad candidate isn't a gate.
- Doc/reality conflicts get a **D-entry** in `docs/07`, never a silent fix.
- **Never weaken a gate to raise yield.** Fix a gate that's *wrong* (D-45, D-49,
  D-57, D-81); never loosen one that's *right*.
- The user's instinct that "it's the pipeline, not the model" was correct **five
  times running**. Take it seriously.
