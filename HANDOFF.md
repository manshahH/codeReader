# CodeReader — Handoff Brief

Paste this into a new chat to resume. Everything else lives in the repo
(`CLAUDE.md`, `docs/00`–`docs/09`, `docs/07-decisions.md` = D-1..D-122).
Forward plan (what to build next) lives in `docs/10-roadmap-retention.md`.

Last refreshed: 2026-07-18 (A1 streak safety net shipped; D-116..D-119).

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

All milestones M0-M8 complete and the app is live end to end in production:
GitHub OAuth login, onboarding, daily session, instant deterministic grading,
streaks, spaced repetition, stats, disputes. The session gate was removed so
reaching `/session` opens the player directly (D-111). Frontend passed a full
Playwright session smoke test and scored 0/16 on the anti-slop audit across every
screen; the Review/Dashboard/Profile screens got a dual-pane + glassmorphism
polish pass (see `docs/ops-incident-report-july-2026.md`). 514 backend tests green
(456 predated A1; A1 took it to 457, A2 added 49, D-121/D-122 added 8).

**Retention layer: A1 (streak safety net) is BUILT; A2 onward is not.** A1 added
freeze accrual and consumption, repair / earn-back, an ops outage freeze, and a
"welcome back" state in place of guilt copy. The load-bearing decision is D-116:
a "covered day" is read from the `streak_events` ledger, not inferred from the
freeze balance, so an outage fills a day for everyone without spending anyone's
balance. New routes: `POST /v1/streak/repair` (idempotent, advisory-locked) and
two admin ops routes (`/admin/streak/outage-freeze`,
`/admin/streak/grant-initial-freezes`). `/v1/me/stats` gained `repair_available`
and `repair_restores_to`. Also D-117 (both `.env.example` files are drift-checked
now; the root one had already drifted) and D-118 (one-time backfill of the
starting freeze balance for pre-A1 accounts, run once after deploy).
**A2 (email capture) is next**; the plan is `docs/10-roadmap-retention.md`.

A1 is **merged but NOT deployed** (plan: build more of Phase A, ship as v2). The
release checklist lives in `docs/09` section 5: backend deploys before frontend,
no migration, no new required env, and one post-deploy backfill call.

Deferred out of A1, deliberately: there is **no session-complete screen**.
`Session.tsx` redirects to the Dashboard when the last exercise is done, so A1's
"dashboard and session-complete" requirement is met on the Dashboard and in the
per-attempt reveal only. Building that screen is its own piece of work.

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

**Pre-beta (from the Fable/Opus whole-system audit):**
- ✅ job runner wired, exercise pull path, transient empty sessions, seed gating,
  difficulty bands (D-58..D-62)
- ✅ Sentry (D-63), rate limits, concurrency locks, streak reconciliation,
  partition recovery, security headers, backup/restore drill (D-64..D-73)
- ✅ **conftest DB wipe** guarded (D-88)
- ⚠️ **rotate secrets** — verify the burned July-12 keys were rotated at provider
- ⚠️ `/admin/metrics` uses a shared-secret token, not real auth (fine for a 20–30
  person beta, flagged)
- ⚠️ alert catalog is **log-only** — nothing actually pages anyone
- ⚠️ CI dependency-audit job has never run against live advisory feeds

**Polish (deferred, agreed):**
- "1 days" pluralization
- streak should render as **gutter ticks**, not a single dot (docs/08 intent)
- **the profile + session-complete screens are sparse and underdesigned** — the
  session player is strong, the surrounding screens need a design pass. Own
  milestone, after content exists.

**Then:** human-review the corpus via `review_cli packet`, flip to live, invite
20–30 devs, watch D1/D7 retention + dispute rate. Beta criterion: a week of daily
sessions with **zero manual intervention**.

---

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
