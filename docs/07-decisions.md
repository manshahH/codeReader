# 07 : Decision Log

Append-only. Every design decision that was questioned, reversed, or settled
with a tradeoff. When implementation diverges from docs 00-06, the divergence
is recorded here first. Format: D-n, decision, why, what it cost.

D-1  Modular monolith + 3 isolated deployables (pipeline, sandbox, grading
     workers), not microservices. Boundaries only where failure/security/
     scaling domains differ. Cost: future extractions need discipline on
     module boundaries now.

D-2  REST over GraphQL. Reads are predictable and must be CDN-cacheable.

D-3  GitHub OAuth only at launch, but provider-agnostic identity tables from
     day one. Teams will force Google/SSO later; that becomes a row type.

D-4  Hybrid tokens: 15-min JWT + opaque rotating refresh. Statelessness on the
     hot path, revocation within 15 min without a denylist. family_id stored
     now; reuse-detection family kill deferred (MVP: log + alert).

D-5  Exercises immutable per (id, version). Correctness feature (stats
     integrity, disputes), not scale. Enables immutable CDN URLs later.

D-6  grading/payload/explanation as separate JSONB columns: the serialization
     boundary IS the security boundary.

D-7  attempts partitioned monthly from day one even on one small box.
     Declaring now = one line; retrofitting = a weekend. Consequence accepted:
     PK (id, created_at), so no FKs to attempts; disputes.attempt_id is a
     soft link.

D-8  Idempotency in Redis only, not a DB constraint (partitioned unique would
     need created_at, defeating it). Accepted: replay after Redis loss can
     duplicate; stats job dedupes.

D-9  Ground truth by execution only; LLM claims are never trusted. Twin-
     snippet invariant for bug types; captured stdout for trace; double-run
     for determinism. The one non-negotiable of the whole product.

D-10 Gates reject, never repair. Repaired candidates inherit inconsistencies;
     regeneration from spec is cheaper. Sole exception: one JSON-parse retry.

D-11 Trace expected_stdout discarded but still compared: generator that
     mis-traces its own code wrote bad distractors too; mismatch rejects the
     whole candidate and the mismatch rate is a template quality metric.

D-12 Trace distractors must be DERIVED from a named misconception, tag stored.
     Quality rule that doubles as future skill-graph data for free.

D-13 "partially_defensible" distractor = hard reject. Arguably-correct
     distractors fail the most careful users, the ones who write disputes.

D-14 Gate model must be a different family (minimum different tier) than the
     generator; models grading their own output inherit their blind spots.

D-15 has_bug=false variant (~15%): trains "most code is fine" judgment; needs
     the defect-audit gate to confirm zero defects.

D-16 No standalone GET /exercises at MVP. Session is the only content
     channel: kills a scraping surface and makes the in-session rule
     enforceable. Cost: no share pages until post-MVP.

D-17 daily_sessions persisted in Postgres, Redis is only a cache. A Redis
     flush must not resample a user's session mid-day.

D-18 Summarize graded inline (6s budget) behind a grade_rubric() seam;
     queue + WebSocket push is a post-MVP swap touching one call site.

D-19 Streak counts even while grading is pending. Our LLM latency must never
     cost a user their streak.

D-20 Clients receive difficulty_band, never raw difficulty numbers.

D-21 text + CHECK instead of Postgres enums; constraint swap beats ALTER TYPE.

D-22 gen_random_uuid() (v4) accepted at MVP; switch to app-generated UUIDv7
     when index locality matters, zero schema change.

D-23 Session pre-builder (nightly bundles) is end-state, not MVP: at MVP DAU,
     build-on-request + Redis cache. The pre-builder is purely a spike
     absorber.

D-24 Sandbox isolation at MVP = separate VM + docker --network=none, no
     gVisor/Firecracker yet, because MVP executes only pipeline-generated
     code. The machine boundary is kept; the runtime hardening arrives with
     community submissions.

D-25 Positioning is verify-AI / review-better, never learn-to-code. Drives
     content (review_the_pr as flagship type), marketing, and the answer to
     "why not just ask Claude".

D-26 Docs numbered 00-07 with a CLAUDE.md index; build prompts reference
     milestones (M0-M8) and doc numbers instead of restating requirements, so
     prompts stay short and the docs stay the single source of truth.

D-27 Design direction is a numbered doc (docs/08), decided before the build,
     because an unpinned design in an agentic build regresses to the
     statistical mean (the slop mechanism). Signature primitive: the gutter.
     Semantic law: red/green reserved for correctness only, never decoration.

D-28 Design skills (anti-slop-frontend, ui-ux-promax) live in .claude/skills/
     inside the repo and are mandatory pre-reads for M6; the slop-catalogue
     audit is part of M6's definition of done, not a suggestion.

D-29 Skills are stored as plain reference docs in skills/ at repo root, not
     .claude/skills/, because the implementation agent is Codex, which has no
     skill auto-loading; design skills are enforced by explicit read
     instructions in the M6 prompt instead of by tooling. AGENTS.md mirrors
     CLAUDE.md for Codex.

D-30 M0 expands the unspecified RATE_LIMIT_* configuration names into
     RATE_LIMIT_DEFAULT_PER_MINUTE, RATE_LIMIT_ATTEMPTS_PER_MINUTE, and
     RATE_LIMIT_AUTH_PER_MINUTE. These map directly to the MVP limits in
     docs/03 and docs/05. Cost: renaming later would need an env migration.
D-31 M2 scopes the refresh cookie to `/v1/auth` instead of the contract
     shorthand `/v1/auth/refresh`, because logout must revoke the presented
     refresh token and browsers cannot scope one cookie to two exact endpoint
     paths. Only `/v1/auth/refresh` and `/v1/auth/logout` read the cookie;
     regular authenticated endpoints still require the access JWT. Cost: the
     browser also sends the cookie to OAuth auth routes, where it is ignored.

D-32 M3 explain.py is a deterministic merge, not a new LLM call: no
     explain_*.md template exists in prompts/, and gates never repair (D-10).
     It takes the generator's draft_explanation and layers the now-verified
     artifacts on top (sandbox-captured stdout for trace; sandbox-confirmed
     bug_lines + the defect_audit gate's confirmed defect for spot_the_bug).
     If the draft doesn't reference the verified facts, the verified facts
     still win but the mismatch is flagged (mismatch_flagged/mismatch_detail)
     for human review rather than silently smoothed over. Cost: an
     inconsistent-but-plausible draft summary ships to review with a flag,
     not a rewritten summary; a human resolves it, not a second LLM pass.

D-33 M3 pipeline/config.py duplicates the env vars it needs (ANTHROPIC_API_KEY,
     GATE_MODEL, GENERATOR_MODEL, SANDBOX_HOST, DATABASE_URL) instead of
     importing app.config, so pipeline stays an independently deployable unit
     per D-1; only pipeline/publish.py imports backend.app (models + the
     existing exercises service), never app.config or any other domain.
     Cost: the two settings modules must be kept in sync by hand.

D-34 M3 dedup's content_hash and the spec sampler's avoid_patterns history are
     stored inside the existing `source` JSONB column (`source.content_hash`,
     `source.bug_mechanism`) rather than new schema.sql columns, since no
     migration was needed to ship M3. Cost: querying by content_hash means a
     JSONB `->>` filter, not an indexed column; revisit if the live pool grows
     large enough for that scan to matter.

D-35 M4 `difficulty_band` mapping (not specified elsewhere): `difficulty_authored`
     1-3 -> `easy`, 4-6 -> `medium`, 7-10 -> `hard`; a slot with `is_boss=true`
     always reports `boss` regardless of its authored difficulty. Cost: none;
     purely a display-layer mapping, tune the thresholds freely later.

D-36 M4 spaced repetition's "right again" interval (21d) is interpreted as
     "this concept has been answered correctly at least once before this
     attempt" (`user_concept_state.correct > 0` prior to the update), not
     strictly consecutive-correct (Leitner-box semantics), because
     `user_concept_state` has no "last result" column and the interval rule
     is explicitly "tune later" in docs/06. Cost: a wrong-then-right-then-right
     sequence reaches the 21d interval on the third attempt same as a
     right-right sequence would; revisit with a dedicated column if the
     product wants strict consecutive-correct streaks.

D-37 M4's session sampler restricts the candidate pool to `spot_the_bug` and
     `trace` only, excluding `summarize`, because POST /attempts only grades
     deterministic types until M5 ships rubric grading. Mirrors the existing
     "if the LLM grader is degraded, summarize slots are replaced at sampling
     time" fallback in docs/05 section 4, just made unconditional until M5.
     Cost: none; M5 removes the type filter as part of wiring grade_rubric().

D-38 M5 "attempted" / session-progress queries (`_remaining_count` in
     attempts/service.py, the `attempted` flag in sessions/service.py) now
     count any submitted `attempts` row for (user, exercise, session_date),
     not just `status='graded'`. Before M5 every attempt reached `graded`
     synchronously so the distinction never mattered; a `summarize` submit
     can now land `grading_pending` (or terminally `grading_failed`), and
     D-19 says grading latency is the product's problem, not the user's --
     that has to hold for session completion, not only the streak. Bumping
     `total_correct`/`accuracy_by_type`/`user_concept_state` is still
     deferred until `is_correct` is actually known (immediately for
     deterministic types and successfully-graded-inline summarize, later via
     jobs/grading_retry.py for one that first lands pending); only the
     "was this exercise submitted" bookkeeping moved. Cost: none identified;
     `exercise_stats`/percentile computation (jobs/percentiles.py) is
     untouched and still filters strictly to `status='graded'`, since
     `is_correct` is meaningless while pending.

D-39 M5 adds `GRADER_MODEL` to config.py/.env.example. docs/06's
     Configuration section listed `GRADER_TIMEOUT_S` but never named the
     model env var itself, even though the M5 milestone scope always implied
     the grader needs its own model (a different concern from `GATE_MODEL`/
     `GENERATOR_MODEL`, which are pipeline-only per D-33 and not even
     imported by the backend). Same pattern as D-30 (expanding an
     underspecified `RATE_LIMIT_*` name into the concrete list actually
     used). Cost: none; purely additive.

D-40 M6 adds `CORSMiddleware` to `backend/app/main.py` (`allow_origins=
     [APP_ORIGIN]`, `allow_credentials=True` for the `rt` cookie). `APP_ORIGIN`
     was defined in config.py since M0 with the comment "CORS + post-OAuth
     redirect" but only the redirect half was ever wired through M5; without
     CORS the SPA's cross-origin fetches to the API are browser-blocked, so
     the frontend could not function at all. Cost: none; the origin allowlist
     was already the intended value.

D-41 M6 implements the disputes endpoint (`backend/app/disputes/service.py`,
     `router.py`, `schemas/disputes.py`), replacing the one-line placeholder
     left in `disputes/router.py` since M5 ("Dispute router placeholder for
     M6"). The `Dispute` table/model already existed; only the endpoint was
     missing, and the M6 screen list includes the dispute modal, so this
     ships with the frontend that calls it rather than shipping a dead
     button. One open dispute per (user, exercise, version); a duplicate
     open dispute returns `409 idempotency_conflict` (contract only reserves
     that code for `POST /attempts`, but no dedicated dispute-conflict code
     is specified in docs/05 section 1's table, and this reuses the closest
     existing semantic rather than inventing a new error code). Cost: none
     identified; docs/05 section 6 gains an implicit conflict-status note if
     revisited.

D-42 M6 adds `users.onboarded` (migration `0001_users_onboarded`, `db/schema.sql`
     updated to match) and implements `PATCH /me` (`users/service.py`,
     `users/router.py`, `schemas/users.py`), neither of which existed before.
     Discovered while wiring the onboarding screen: `auth/service.py`'s
     `user_response()` hard-coded `"onboarded": True` unconditionally (no
     column backed it), so `RootGate`'s "route to /onboarding vs /session"
     logic -- required by docs/03's screen list and docs/05's `user.onboarded`
     field -- had no real signal to route on, and there was no endpoint to
     persist the level pick at all. Setting `level` via `PATCH /me` is treated
     as the onboarding action itself (docs/03 defines onboarding as exactly
     "level pick, one screen"); no separate "mark onboarded" call exists.
     Cost: one migration; existing rows default to `onboarded = false`, so
     any pre-M6 seeded/test user will be routed to onboarding once on first
     post-upgrade login, then proceeds normally.

D-43 M6 adds `GRADER_PROVIDER` (`anthropic` default | `openai`) and an
     `OpenAIGraderClient` alongside the existing `AnthropicGraderClient`
     (`attempts/grader_client.py`), selected in `get_default_grader_client()`.
     Reason: the M6 Playwright smoke test needs the summarize exercise to
     actually reach `status="graded"` through the real inline rubric grader
     (docs/06 D-18), but this environment's compose `.env` only had a
     placeholder `ANTHROPIC_API_KEY` -- every real grading call failed auth
     and, per `rubric.py`'s catch-all (`except Exception: raise
     RubricGradingTimeout`), landed permanently in `grading_pending` with no
     path to `graded` or `grading_failed`. A real OpenAI key was available
     instead, so `GRADER_PROVIDER=openai` + `GRADER_MODEL=gpt-4o-mini` +
     `OPENAI_API_KEY` are set only in `docker-compose.override.yml` (already
     gitignored, never committed); the tracked `docker-compose.yml` and
     `.env.example` keep `GRADER_PROVIDER=anthropic` as the default. `rubric.py`
     and `attempts/service.py` are untouched -- `GraderLLMClient` was already
     a provider-agnostic seam (D-18), so this is purely an additive client +
     a provider switch. Cost: two LLM SDKs (`anthropic`, `openai`) are now
     backend dependencies instead of one; revisit if that's unwanted
     long-term, but the grader is a single, isolated call site either way.

D-44 Content pipeline (`pipeline/llm_client.py`, `pipeline/config.py`) is
     OpenAI-only by default, same reasoning as D-43 one level up the stack:
     this environment has a real `OPENAI_API_KEY` but only a placeholder
     `ANTHROPIC_API_KEY`, and the generator/gates must actually run, not just
     import cleanly. `OpenAILLMClient` is added alongside `AnthropicLLMClient`
     (same `LLMClient.complete()` shape, sync `openai.OpenAI(...)` call
     mirroring `OpenAIGraderClient`'s pattern), selected via a new
     `build_llm_client(provider, model)` factory that `orchestrator.py`'s
     `main()` calls once per role, driven by new `GENERATOR_PROVIDER` /
     `GATE_PROVIDER` settings (both default `"openai"`) plus the existing
     `GENERATOR_MODEL` / `GATE_MODEL`. `PipelineSettings.ANTHROPIC_API_KEY`
     drops its `Field(..., min_length=1)` requirement (default `""`) so the
     module imports and `PipelineSettings()` constructs with no Anthropic key
     present at all; each client instead validates its own provider's key
     lazily inside `_get_client()`, at first `complete()` call, raising a
     `ValueError` naming the missing var (`ANTHROPIC_API_KEY` or
     `OPENAI_API_KEY`) rather than the SDK's opaque auth error. D-14's
     `assert_gate_and_generator_models_differ()` is untouched -- it compares
     model strings, not providers, so a same-model conflict still fires
     regardless of which provider(s) are in play. `generate.py` and
     `semantic_gates.py` are untouched: they already only depend on the
     `LLMClient` protocol via an injected parameter, never construct a
     client themselves, so the only real construction site is
     `orchestrator.py`. `openai` was already a backend dependency (D-43); no
     new package to add, since the pipeline runs in the same environment
     (backend's venv -- pipeline has no pyproject.toml of its own, api only
     mounts `backend/`). Cost: none identified; purely additive wiring plus
     one relaxed field constraint.

D-45 `sandbox_gate.py` check 5 (`bug_lines_match_diff`) now diffs buggy_code
     vs fixed_code with `difflib.SequenceMatcher` instead of a positional
     index-by-index zip. Diagnosed against real gpt-4.1 generations: a naive
     zip diff treats any line INSERTED or DELETED by the fix as shifting
     every following line, so it reports the whole tail of the file as
     "changed" even when the model's fix is a correct, minimal, single-line
     edit -- e.g. a fix that adds `import threading` at the top and then
     acquires a lock on the actual bug line could never pass, by
     construction, no matter how precisely the model identified the bug.
     That check was rejecting essentially every real candidate (12/13 in a
     diagnostic probe), not just malformed ones. The check's intent was
     always "the fix changes exactly the declared lines and nothing else,"
     not "the fix must preserve line count" -- the zip diff was an
     implementation bug in the trust gate itself, not a legitimate
     tightening of it. Fix: `_diff_changed_lines` now walks
     `SequenceMatcher.get_opcodes()` and collects buggy_code's own (pre-fix)
     1-indexed line numbers from every `replace`/`delete` opcode; `insert`
     opcodes contribute no original line numbers, so a fix may freely add
     lines (new import, new guard, wrapping in `with`) alongside a real
     change without being penalized for the insertion. This does not weaken
     the check: a change to any undeclared original line still fails it (two
     opcodes instead of one), a declared bug line the fix never actually
     touches still fails it (empty diff, non-empty `bug_lines`), and
     `has_bug=False` is handled separately and unchanged in strictness --
     `fixed_code` must still be byte-identical to `buggy_code` with
     `bug_lines == []`, full stop, diff opcodes aside. `autojunk=False` on
     the matcher: its default "common lines are junk" heuristic is a speed
     hack irrelevant at this file size (line budgets top out at 60) and not
     worth the risk of misclassifying a frequent short line (a blank line, a
     `return` statement) on the pipeline's trust gate. Applied identically to
     `prompts/dryrun_stb_validation.py`, which already imported `difflib` but
     never called it -- the reference script and the real gate must stay
     mechanically identical, per its own module docstring. Verified before
     and after: the dry-run's known-good candidate and every existing M3
     sandbox_gate test still pass; four new tests cover the fix directly (an
     inserted-import-plus-real-fix candidate now PASSES; a fix touching an
     undeclared line, and one that only inserts without ever touching the
     declared line, both still FAIL; a `has_bug=False` candidate with any
     `fixed_code` difference still FAILS). The other four checks are
     untouched. Cost: none identified -- strictly closes a false-rejection
     hole without opening a false-acceptance one.

D-46 `prompts/generator_spot_the_bug_python_v1.md` constraint 8 (the
     "fixed_code MUST have the exact same number of lines as buggy_code,
     pre-plant an unused/misused supporting line instead of inserting one"
     rule) is reverted; a live gpt-4.1 probe (8 then 15 then 15 candidates,
     `pipeline/_probe_static_gate.py`, deleted after use) showed it was the
     direct cause of a chunk of the post-D-45 static_gate rejection spike.
     Concretely: constraint 8's own worked example named `import threading` /
     "creating a lock" as the way to pre-plant a supporting line -- but
     `threading` is on both constraint #2's forbidden-imports list and
     `static_gate.FORBIDDEN_IMPORTS`. The model followed the instruction
     literally (a `RecommendationEngine` with `from threading import Lock`
     and `self._lock = Lock()` used throughout via `with self._lock:`,
     entirely plausible production code, not litter) and static_gate
     correctly rejected it as a forbidden import -- the prompt was telling
     the model to do the one thing constraint #2 forbids. Separately,
     fixed_code not landing at the same line count as buggy_code (either
     because the model didn't comply with constraint 8, or because avoiding
     insertions pushed it toward terser code) was pushing fixed_code outside
     the sampled line_budget on its own. D-45 already made the sandbox gate's
     diff (`_diff_changed_lines`) correctly credit insertions alongside a
     real replace/delete, so constraint 8's line-count mandate no longer
     protects anything the gate doesn't already handle. Fix: constraint 8 now
     allows insertions/deletions, forbids pre-planting dead-or-misused
     scaffolding outright, requires at least one existing line's text to
     actually change (a pure-insertion fix gives `bug_lines == []`, which is
     indistinguishable from `has_bug=false` and unreviewable), and adds a
     worked example computing `bug_lines` for an insert+replace fix.
     Constraint 9's bug_lines instructions were updated from "compare line by
     line, position by position" (the same naive-zip framing D-45 fixed in
     the gate itself) to "align like a real diff, record only replaced/
     deleted original lines." Constraints 9's "computed not estimated" and
     10's trailing-newline requirement are untouched. No gate code changed.
     Verified: a 15-candidate post-fix probe against real gpt-4.1 produced
     zero forbidden-import-from-scaffolding and zero hinting-name rejects
     (11/15 static_gate pass; the remaining 4 were pre-existing, unrelated
     issues -- 3 candidates undershooting a tight line_budget at low/mid
     difficulty, 1 `resource-leak-unclosed-file` candidate needing `open()`,
     which constraint #2 and static_gate both already forbid outright,
     a taxonomy/concept-vs-forbidden-list conflict that predates this prompt
     and this diagnosis). Cost: those two remaining issues are real but
     out of scope here -- not caused by constraint 8, and not touched.

D-47 `pipeline/llm_client.py`'s `OpenAILLMClient` and
     `backend/app/attempts/grader_client.py`'s `OpenAIGraderClient` both send
     `max_tokens` unconditionally, which gpt-5-family and reasoning models
     (`o1`, `o3`, `o4`) reject outright: "Unsupported parameter: 'max_tokens'
     is not supported with this model. Use 'max_completion_tokens' instead"
     (HTTP 400) -- both call sites were unusable with any generator/grader
     model newer than gpt-4. Fix: a `_token_limit_kwarg(model)` helper
     (duplicated in both files, same reasoning as D-33/D-43 keeping the
     pipeline and backend independently deployable) does a prefix check --
     `gpt-4`/`gpt-3` -> `max_tokens`, everything else (`gpt-5*`, `o1`, `o3`,
     `o4`, and any unrecognized future family) -> `max_completion_tokens` by
     default. `complete()` sends the request once with that choice; on any
     exception it inspects the error text and retries exactly once with
     `max_tokens` swapped in if the message names `max_tokens` (covers an
     ambiguous family guessed wrong) and/or `temperature` dropped if the
     message names `temperature` (gpt-5-family reasoning models can 400 on a
     non-default temperature). A second failure after that one retry still
     raises -- this is a targeted compatibility shim, not a generic retry
     loop. gpt-4* behavior is unchanged: it always resolves to `max_tokens`
     up front and the retry branch is a no-op unless the API actually 400s.
     No pipeline/gate logic touched -- both files still only build
     provider clients; `generate.py`, `semantic_gates.py`, `rubric.py`, and
     `attempts/service.py` are untouched. Cost: one string-matching retry
     path per client; if OpenAI ever wraps 400s in a structured error type
     instead of a message string, this degrades to always raising on the
     first attempt (safe failure, not silent misbehavior).

D-48 Every REJECTED candidate now persists its full validation report
     (`pipeline/publish.py` `write_reject_report`, called from
     `orchestrator._record_reject`) to `validation_reports_dir/rejects/`,
     named `{stage}_{concept}_{suffix}.json` and containing the stage, the
     spec, the candidate's code, and every gate check's name/passed/detail
     (including sandbox stderr). Previously only PUBLISHED candidates kept
     receipts; a reject was a bare counter, so each diagnosis (D-45, D-46,
     D-47 all began as paid probe runs) cost real tokens. BatchReport also
     gains per-concept counters (`concept:{slug}:rejected/published/
     exhausted`), so a permanently-dead concept is visible in the batch
     summary instead of hiding in aggregate noise (the observability half of
     the audit's M6 finding). Cost: report files accumulate on disk;
     rotation/cleanup is left to ops (same as the existing published-report
     files).

D-49 sandbox_gate check 5 no longer requires the generator's declared
     `bug_lines` to exactly equal the diff -- the answer key is now DERIVED:
     `_diff_changed_lines(buggy, fixed)` (the same SequenceMatcher diff D-45
     introduced, anchored by the executed twin-snippet from checks 1-2)
     becomes `SandboxGateResult.verified_bug_lines`, which the orchestrator
     feeds to defect_audit, the solver key, explain, and publish. The old
     check was a line-number transcription test orthogonal to exercise
     quality: the pipeline computed the ground truth and then rejected the
     candidate for the model's arithmetic differing from it. Deriving
     STRENGTHENS the trust story -- the shipped key is diff-of-execution-
     proven-twins, never a model claim that happened to match (this also
     makes prompts/README contract #3's "the pipeline re-derives bug_lines"
     actually true). The check (renamed `fix_diff_real_and_minimal`) still
     REJECTS: an empty diff with has_bug=true (pure-insertion fix, nothing
     for the exercise to point at, indistinguishable from has_bug=false, per
     D-46), and a rewrite-sized diff (over max(5 lines, 20% of the file) --
     a smeared diff makes every changed line a "correct" answer, i.e. no key
     at all). has_bug=false is byte-identical-or-reject, unchanged. A
     claim-vs-diff mismatch is logged (`bug_lines_claim_mismatch`, counted as
     `stb_bug_lines_claim_mismatch` per batch) as a template-quality metric,
     D-11 style. Applied identically to prompts/dryrun_stb_validation.py.
     KNOWN SEMANTIC CHANGE to one existing negative test: a fix that changes
     the declared line AND cosmetically rewrites an undeclared line (the
     D-45-era `_FIXED_CODE_WITH_UNDECLARED_CHANGE` fixture) is now ACCEPTED
     with the derived key [2, 4] and a logged mismatch, where it used to
     reject. That is this decision's explicit trade: the cosmetic extra line
     becomes part of the key and the mismatch flag routes it to human
     review; the alternative (rejecting on any claim/diff disagreement) is
     exactly the transcription test being removed. The test was rewritten to
     assert the new contract.

D-50 sandbox_gate joins buggy_code/fixed_code with test_code via
     `_concat_snippets`, inserting the "\n" separator when the code does not
     already end with one, instead of raw string concatenation. A generator
     that dropped the trailing newline glued its last code line to the
     test's first line: SyntaxError, checks 1-2 fail, an invisible false
     reject (the audit's Defect B; the old mitigation was prompt constraint
     10 begging for trailing newlines, plus a README-promised normalization
     no code performed). Inserting the separator is deterministic and can
     only repair syntax the concatenation itself broke, never a false
     accept. Prompt constraint 10 is dropped in the v2 template (D-53).
     Applied identically to prompts/dryrun_stb_validation.py.

D-51 The static gate's line budget now applies to buggy_code (and trace code)
     only; fixed_code is checked with line_budget=None (all other checks --
     forbidden imports/calls, hint words, secrets -- still run on both
     snippets; `static_gate.check` grew the None option). The budget is a UX
     constraint on what the user READS, which is never fixed_code; after
     D-46 explicitly invited insertion fixes, a buggy_code near
     line_budget_max plus a two-line fix overflowed the budget and
     false-rejected (the audit's Defect D, directly undercutting D-46).
     Cost: none identified; a pathologically bloated fix is still caught by
     D-49's rewrite cap and by review.

D-52 The solver semantic gate accepts ANY verified bug line, not only
     bug_lines[0]: `semantic_gates.solver()` gains `acceptable_lines`, and
     the orchestrator passes the sandbox-verified lines (D-49). For a
     multi-line bug, a solver naming the second verified line was a correct
     answer being rejected as "confidently mis-keyed" at confidence >= 0.8
     -- a latent D-45-class defect that no candidate had yet reached only
     because none had survived the sandbox. A line NOT in the verified set
     still rejects/flags exactly as before; reason_id must still match
     exactly.

D-53 `prompts/generator_spot_the_bug_python_v2.md` (prompt_template_id
     stb_py_v2) replaces v1; generate.py points at it. Two content changes:
     (a) v1's constraint 10 (trailing-newline requirement) is dropped, made
     redundant by D-50; (b) a new test constraint 13 with a worked example
     shows the exception-to-assertion wrap (try/except the trigger call,
     raise AssertionError) -- v1's constraint 3 explicitly allowed
     exception-raising bugs on non-obvious inputs while sandbox check 1 only
     recognizes AssertionError as a legitimate failure, so
     exception-manifesting concepts (dict-mutation-during-iteration,
     recursion-missing-base-case, ...) were structurally rejected unless the
     model invented the wrap pattern unprompted (the audit's Defect C). The
     gate is NOT relaxed; the prompt now teaches the only pattern that
     satisfies both constraints. The version bump also repairs D-46's
     in-place edit of v1, which violated prompts/README's "any edit bumps
     the version into a new file" contract; v1 stays on disk for
     traceability but reflects its post-D-46, not original, state.

D-54 `taxonomy.Concept` gains `requires_forbidden: str | None`; a flagged
     concept names the forbidden construct it cannot be written without and
     is excluded from `concepts_for_type()`, so the spec sampler never emits
     it. Flagged: `resource-leak-unclosed-file` (needs open()/file I/O,
     forbidden by both static_gate and prompt constraint 2 -- D-46 already
     watched it burn a full round) and `retry-without-backoff` (backoff
     needs `time`, and an unbounded retry can only fail by sandbox timeout,
     never AssertionError, so no valid twin-snippet exists). Each sampled
     doomed spec previously cost MAX_ATTEMPTS_PER_SPEC = 3 full generate+
     gate rounds, ~5% of uniformly-sampled STB spend. Flagged, not deleted:
     a future narrow allowance (e.g. permit open() for the resource-leak
     concept specifically) re-enables one by clearing the field.
     `get_concept()` still resolves flagged slugs, so already-published
     exercises keep resolving.

D-55 `OpenAILLMClient` resolves temperature support UP FRONT by model family
     (gpt-5*/o1/o3/o4 never receive a temperature kwarg) instead of sending
     it, eating the guaranteed 400, and retrying without it. The D-47 shim
     was correct as a compatibility net but doubled every request against
     rate limits for known-fixed-temperature families, and its silent
     temperature drop also concealed that the semantic gates' documented
     temp-0 design was not being honored on those models -- now a logged
     warning (once per client) instead of silence. gpt-4*/gpt-3* behavior
     is byte-identical; the runtime 400-fallback remains for unknown future
     families. backend/app/attempts/grader_client.py keeps the plain D-47
     shim: the grader defaults to gpt-4o-mini (D-43) and was out of this
     change's scope.

D-56 docs/01's cost model updated: ~50% end-to-end survival was optimistic
     for this gate design; compounding realistic per-stage pass rates
     (generation/schema ~0.9, static ~0.75, sandbox/claim-match ~0.5-0.65,
     semantic ~0.65, dedup ~0.95) lands at ~20-30%. The response is
     "generate more", not "loosen gates": per-candidate cost with a
     gpt-4.1-class generator keeps cost-per-shipped inside the original
     envelope, and the strict gates (trace claim-match D-11,
     partially_defensible D-13, defect_audit exactly-one, double-run
     determinism) are the trust product and stay untouched.

D-57 The sandbox had never executed a single generated candidate in the real
     (containerized) pipeline deployment: `pipeline/sandbox/runner.py`
     delivered code via a read-only bind mount
     (`-v <tmp_path>:/sandbox/code.py:ro`) where `<tmp_path>` was a file
     written by the caller's own process. That path is only host-visible
     when the caller runs on the same machine as the Docker daemon. In the
     real deployment the orchestrator itself runs inside a container
     (docker.sock mounted, sandbox containers spawned as siblings), so
     `<tmp_path>` was a path inside the *pipeline* container's filesystem --
     invisible to the host daemon. Docker's response to a bind-mount source
     that does not exist is to silently create an empty directory there, so
     every candidate hit `python -I -B /sandbox/code.py` on a directory:
     "can't find '__main__' module", exit_code != 0, captured_stdout always
     "". Indistinguishable from a real candidate failure, so every sandbox
     check that depends on execution (`buggy_fails_test`,
     `fixed_passes_test`, `buggy_runs_clean`, `code_runs_clean`,
     `deterministic_double_run`) rejected 100% of candidates, silently. This
     was invisible to the existing M3 sandbox tests because they run from
     the host (where `<tmp_path>` IS host-visible) and to
     `prompts/dryrun_stb_validation.py` because it never touches Docker at
     all (`exec()`, in-process, by design -- see its own module docstring).
     Fix: delivery moved to stdin -- `docker run -i --rm ... IMAGE timeout
     -k 1 <n> python -I -B -`, with the candidate source passed as
     `subprocess.run(..., input=code)` instead of a mount. No path is ever
     resolved by either side, so the class of bug cannot recur regardless of
     where the caller runs. No isolation guarantee is weakened:
     --network=none, --read-only, tmpfs /tmp, memory/cpu/pids limits,
     cap-drop=ALL, non-root, no host env vars, and double-run determinism
     are all unchanged. Also added `runner.verify_sandbox_available()`: a
     canary (`print(<token>)`) run through the exact same delivery path
     (`_run_container`), called once at the top of
     `orchestrator.run_batch()`; a mismatched/empty canary result raises
     `SandboxUnavailableError` immediately instead of letting a batch run to
     completion silently rejecting everything. Regression tests added in
     `backend/tests/test_m3_sandbox.py`:
     `test_sandbox_run_python_actually_executes_and_returns_nonempty_stdout`
     (asserts a trivial `print("ok")` returns non-empty, correct stdout --
     the exact assertion the old code path could never satisfy in the
     containerized-caller case), `test_verify_sandbox_available_passes_
     against_the_real_docker_sandbox`, and `test_verify_sandbox_available_
     raises_loud_when_delivery_is_broken` (monkeypatches `_run_container` to
     reproduce the old failure signature and asserts the canary raises
     rather than passing through). `prompts/dryrun_stb_validation.py` is
     unchanged: its sync obligation (D-45) covers the five check *semantics*
     it mirrors via `exec()`, not the Docker transport, which it never used.

D-58 Live-exercise immutability is CONTENT immutability, not row freezing:
     `update_exercise_fields` now permits status-only transitions on a live
     row (to 'pulled' or 'retired' only; any content column alongside, or
     any other target status, still raises ExerciseImmutableError). Before
     this, the guard raised on ANY update of a live row, so docs/00's #1
     kill-risk mitigation ("fast pull of a wrong exercise") had no working
     code path: nothing could set a live row to 'pulled', and an incident
     meant hand-written SQL with no cache invalidation. New
     `exercises.service.pull_exercise()` flips status to 'pulled' AND purges
     every still-servable daily session referencing the exercise
     (daily_sessions rows from yesterday onward plus their
     session:{user}:{date} Redis keys; commit before the Redis deletes so a
     racing GET cannot re-cache a row about to disappear). Wired as
     `python -m pipeline.review_cli pull <id> <version>` via a new
     publish.pull(). publish.kill() on a live row now retires instead of
     raising, but without the purge; pull is the incident path. M1's
     immutability test ENCODED the bug as correct behavior (it proved a live
     row rejects all updates); it now asserts content-and-bad-status
     rejection plus the permitted pulled transition, and
     test_m7_pull_exercise.py proves a pulled exercise disappears from both
     cached and freshly built sessions. Cost: 'status' can no longer be
     frozen per-version by the service guard; the transition allowlist is
     the new fence.

D-59 A zero-candidate session build is transient, never persisted or cached.
     `_build_and_persist_session` returned [] into the same
     persist-and-cache path as a real session, so the first user to open
     their day against an empty live pool got a daily_sessions row with
     exercise_list=[] plus a 36h Redis cache of [], and get_today_session
     reported completed=true -- an empty "done" day that survived content
     restoration. Now: empty slot lists return without persisting or
     caching, the response is completed=false with exercises=[], and an
     already-persisted empty row (pre-fix damage) is deleted and rebuilt on
     the next fetch. The existing "Nothing to read today" frontend copy
     covers the empty payload. Tests seed an actually-empty pool
     (test_m7_empty_session.py), the scenario every prior test avoided by
     always seeding first.

D-60 The periodic-job layer is now actually invoked: `app/jobs/runner.py`
     starts plain-asyncio worker tasks from the FastAPI lifespan
     (JOBS_ENABLED=false opts out, e.g. for ASGI-transport tests).
     grading_retry every 30s, percentiles hourly, partitions daily with a
     run at startup (CREATE IF NOT EXISTS makes the extra ticks free; a true
     monthly interval never fires in a process that restarts more often than
     monthly). Chosen over APScheduler (docs/06 pins "plain asyncio workers
     + cron", and CLAUDE.md forbids substituting libraries; this adds zero
     dependencies) and over a separate cron container (one process to
     deploy/monitor at MVP scale; each job also has a __main__ --
     `python -m app.jobs.grading_retry|percentiles|partitions` -- so
     moving to external cron later is a compose change). Job failures are
     isolated and counted, never fatal. The shipped gap was jobs tested only
     in isolation, so test_m7_jobs_runner.py asserts through the real
     lifespan: the scheduler ticks every job, a genuinely
     grading_pending attempt is resolved by the running app, and the
     next-month partition exists after startup. Frontend: Session.tsx's
     grading poll now stops after 2 minutes (MAX_POLL_MS) into a
     "we'll grade this shortly, your streak counted" state with a Next
     button, so a stuck grade can never freeze the session. Cost: in-process
     jobs share the API's event loop; heavy jobs would need the cron-
     container escape hatch.

D-61 Levels now sample within a difficulty BAND (junior 1-5, mid 3-8,
     senior 5-10), not just toward a target. Closest-to-target alone let a
     thin pool serve a junior a difficulty-8 exercise and a senior a
     difficulty-2 one. Non-boss slots come from the band whenever the pool
     supports it; a due concept whose only exercises are out of band is
     deferred (spaced repetition waits) rather than served; curriculum fill
     is in-band only; out-of-band closest-by-difficulty returns solely to
     keep the session at the MIN_SLOTS floor. The boss slot must sit between
     the band floor and band_top+2 (capped at 10); if nothing fits, the
     session ships without a boss unless it would fall under MIN_SLOTS.
     Also: exercises.difficulty_empirical (schema column, previously
     unused) is now written by the percentiles job as a linear map of
     solve_rate onto 1-10 once >= 30 graded attempts exist (first-cut
     formula: 1 + 9*(1 - solve_rate), clamped), and the sampler prefers it
     over difficulty_authored at the same threshold; it is derived
     operational data, not content, so the D-58 guard is not implicated
     (only the stats job writes it, via SQL). difficulty_band shown to
     clients still derives from difficulty_authored (D-35 display mapping
     unchanged). Cost: a mis-authored difficulty now self-corrects only
     after 30 attempts; below that the band can still misplace an exercise.

D-62 Seed scripts refuse to run without CODEREADER_ALLOW_SEED=1 and
     validate every concept slug against the pipeline taxonomy
     (scripts/seed_guard.py). seed_e2e.py inserted DETERMINISTIC
     spot_the_bug/trace exercises straight to status='live',
     human_reviewed=true with hand-asserted answer keys never proven by
     execution -- exactly what invariant 1 forbids -- and nothing stopped it
     running against whatever DATABASE_URL pointed at. The flag makes
     seeding a conscious, per-invocation opt-in for disposable databases
     (the Playwright flow just sets the env var); status stays 'live' under
     the flag because requiring manual approval would break the e2e
     bootstrap the script exists for. The trace seed's concept
     "list-indexing" was not in the taxonomy and polluted
     user_concept_state on every attempt; it is now "off-by-one" (the
     misconception its distractors actually encode). The summarize seeds
     already used valid slugs and keep their by-design hand-authored rubric
     (no execution oracle exists for summarize). Negative tests:
     test_m7_seed_guard.py proves the no-flag refusal and the
     unknown-slug refusal.

D-63 Sentry wired ahead of the rest of M7 (docs/06's "Sentry; dashboard..."
     scope item), backend (`app/core/sentry.py`, `sentry-sdk[fastapi]`) and
     frontend (`lib/sentry.ts`, `@sentry/react`), both no-ops when their DSN
     env var is unset -- the common local-dev case must never break. New
     `SENTRY_ENVIRONMENT` setting (default "development") added to
     config.py/.env.example alongside the existing `SENTRY_DSN` (present
     since M0 but never consumed until now). PII scrubbing is a `before_send`
     hook on both SDKs, not a config flag, because CLAUDE.md invariant 6
     (user free text is hostile input) and the credentials this app holds
     make it mandatory, not optional: backend strips the `rt` refresh
     cookie, the `Authorization` header, and the entire request body
     (summarize `answer.text` lives there) from every event, and separately
     scrubs any stack-frame local variable whose VALUE matches a live
     `*_API_KEY`/`*_SECRET`/`TOKEN_ENC_KEY`/`JWT_SECRET` env var -- a
     name-based scrub alone would miss a secret captured under an unrelated
     variable name via sentry-sdk's default local-variable capture.
     Frontend mirrors the discipline with `sendDefaultPii: false` and a
     `beforeSend` that drops `event.request.data`/`cookies` and any
     `Authorization` header. `backend/tests/test_m7_sentry.py` asserts the
     scrub directly (crafted event with a fake token and answer text, both
     redacted) and that `create_app()` boots with `SENTRY_DSN` unset.
     Debug-only verification endpoint `GET /v1/debug/sentry-test` is KEPT,
     gated on `SENTRY_ENVIRONMENT != "production"` (chosen over deleting it:
     it is the fastest way to confirm delivery after any future Sentry
     config change, and the gate makes it inert in prod). The frontend throw
     trigger used for the same verification was temporary and has been
     removed. The existing `request_id` (core/errors.py, already returned to
     clients in every error body) is attached as a Sentry tag on every
     request via `sentry_sdk.set_tag` in the `add_request_id` middleware --
     safe to call unconditionally, a no-op when Sentry was never
     initialized -- so a user-reported request_id is directly searchable in
     Sentry.
     Fallout discovered while verifying "tests green with SENTRY_DSN unset":
     several test modules import `app.main` at module scope, which runs
     `create_app()` (and now `init_sentry()`) at pytest COLLECTION time, and
     pydantic-settings resolves `Settings`' `env_file=".env"` relative to
     cwd -- pytest's cwd is the repo root, where the untracked, gitignored
     root `.env` (not `backend/.env`) carries a real `SENTRY_DSN` for local
     compose use. Every plain test run was therefore silently initializing
     a real Sentry client and sending live telemetry before any test or
     fixture executed. Fixed with a module-level (not fixture-scoped)
     `os.environ.setdefault("SENTRY_DSN", "")` in `backend/tests/conftest.py`,
     which loads before collection and beats the `.env` file in
     pydantic-settings' precedence; any test that wants Sentry actually
     active still can via its own `monkeypatch.setenv`. Cost: one
     ops-adjacent module-level line in conftest.py; no test logic changed.
