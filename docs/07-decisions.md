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

D-64 M7 rate limiting is now enforced on EVERY route via a global default
     middleware (app/main.py::default_rate_limit, 60/min per docs/05, keyed
     on the JWT sub when present else client IP), not just the routes that
     happened to call check_token_bucket themselves (previously only auth
     and POST /attempts; /session/today, /me*, disputes, GET
     /attempts/{id}, and the new /admin/metrics had none at all). Auth
     (10/min per IP) and POST /attempts (10/min per user) keep their own
     stricter self-enforcement and are exempted from the default
     middleware rather than double-limited. Same fix closes a real bypass:
     auth/router.py::_client_ip read the LEFTMOST (client-suppliable)
     X-Forwarded-For entry, so an attacker rotating that header got a
     fresh rate-limit bucket key every request and the 10/min auth limit
     never actually engaged. app/core/network.py::resolve_client_ip now
     reads the RIGHTMOST TRUSTED_PROXY_COUNT entries instead (new setting,
     default 1, matching docs/03's single-LB topology) -- the hop(s) a
     real trusted proxy appends, never a value the client itself can set.
     TRUSTED_PROXY_COUNT=0 disables XFF trust entirely and falls back to
     the raw TCP peer; this must be set correctly for the actual proxy
     count in front of any real deployment (documented in
     docs/ops-runbook.md) or the limit is either bypassable (set too high)
     or wrongly rejects real users behind a shared NAT/proxy (set too
     low). Cost: one new required-to-tune setting; wrong in either
     direction has a real security or availability effect, not just
     cosmetic.

D-65 POST /attempts' idempotency-replay path skipped the rate-limit check
     entirely (only a fresh submit called check_token_bucket), so a replay
     response shipped with no X-RateLimit-* headers at all -- violating
     docs/05 section 1's "headers on every response." Fixed by moving the
     rate-limit check to the top of submit_attempt, before the idempotency
     cache lookup, so it runs (and its headers attach) unconditionally.
     Cost: a pure replay now also consumes one token from the attempts
     bucket; accepted as correct, not a regression -- it's still an API
     call hitting the rate limiter, and docs/05 draws no replay exemption.

D-66 M7 concurrency fix for POST /attempts (the audit's headline bug): two
     concurrent submits for the same (user, exercise, session_date) -- two
     tabs, or a network retry racing the still-in-flight original -- used
     to both miss the idempotency cache, both pass the already-attempted
     SELECT (no row lock, and the partitioned attempts table can't carry a
     DB unique constraint, D-7), both INSERT, and both run the
     stats/streak read-modify-write (lost update on total_attempts, a
     possible duplicate streak_events row). Two layered fixes, covering
     the two distinct races CLAUDE.md's audit named:
     (a) app/core/idempotency.py gains a Redis SET NX reservation
     (acquire_reservation/wait_for_cached/release_reservation) on the
     Idempotency-Key itself: the loser of a same-key race waits for the
     winner's stored result and replays it byte-identically instead of
     racing it -- this is the "network retry racing the original" case,
     where both requests share one key.
     (b) A Postgres transaction-scoped advisory lock
     (pg_advisory_xact_lock(hashtext(user_id), hashtext(exercise_id ||
     session_date))) around the check-through-insert in the new
     _build_and_store_attempt (the code that used to be the back half of
     submit_attempt) -- this is the "two tabs" case, where each tab holds
     its OWN Idempotency-Key and a same-key reservation alone cannot
     serialize them. The lock is the real backstop regardless of which (or
     how many) Idempotency-Keys are in play; the loser observes the
     winner's committed row via the existing already-attempted SELECT and
     correctly 409s. Verified with REAL concurrency (asyncio.gather, not
     sequential awaits) in
     backend/tests/test_m7_ratelimits_and_concurrency.py: same-key double
     submit -> both responses 200 with the identical attempt_id, exactly
     one attempts row, total_attempts incremented by exactly 1;
     different-key double submit -> one 200 + one 409, same row/stats-count
     guarantee. Cost: one extra Redis round-trip per attempt submit (the
     reservation) and a lock held for the duration of the grading call for
     summarize (up to GRADER_TIMEOUT_S) -- scoped to a single (user,
     exercise, day) tuple, so it only ever serializes against a genuine
     duplicate submit of the exact same exercise by the exact same user on
     the exact same day, never unrelated traffic.

D-67 D-8's claim that "the stats job dedupes" a Redis-idempotency-loss
     replay duplicate was FALSE -- nothing deduped. jobs/percentiles.py
     counted every status='graded' row with a bare count(*) ... GROUP BY
     exercise_id, exercise_version, so a duplicate attempts row (the exact
     scenario D-8 describes, now much rarer after D-66 but not
     structurally impossible) permanently inflated a percentile's n and
     skewed its solve rate; user_stats.total_attempts/total_correct are a
     separate, non-aggregated path (incremented directly in the request
     transaction) and are actually protected by D-66's advisory lock, not
     by this fix. Fixed: the query now dedupes to one row per (user_id,
     exercise_id, exercise_version, session_date) -- the earliest-created
     graded attempt, via DISTINCT ON -- before counting.
     backend/tests/test_m4_stats.py::test_compute_exercise_stats_job_aggregates_attempts_into_exercise_stats
     used FOUR attempts from the SAME user on the SAME day as its
     aggregation-math fixture, which is now exactly the "duplicate" shape
     dedup collapses to one row; rewritten to use four DISTINCT users (a
     realistic shape -- one graded attempt per user per exercise per day is
     the actual invariant), with a new
     test_compute_exercise_stats_dedupes_duplicate_attempt_rows covering
     the dedup behavior itself directly. Same fixture bug existed in
     test_m7_sampler_bands.py's difficulty_empirical threshold test (30
     same-user-same-day attempts); fixed by spreading them across 30
     distinct session_dates instead. This D-entry corrects D-8's false
     claim rather than editing it in place, per docs/07's own append-only
     rule. Cost: one extra CTE per percentiles run; negligible at MVP
     write volume.

D-68 M7 streak reconciliation on a timezone change (docs/05 section 3:
     "changing timezone never retroactively breaks a streak (the
     reconciliation job handles the boundary day)" -- previously an
     unimplemented promise; jobs/streak_recon.py was a one-line placeholder
     and users/service.py::update_me just wrote the new timezone with no
     reconciliation at all). A user-local "today" is a function of both the
     instant and the timezone; a WESTWARD change (e.g. Pacific/Kiritimati
     UTC+14 -> Pacific/Midway UTC-11, a ~25h swing) can move the new local
     "today" EARLIER than the already-recorded
     user_stats.last_active_local_date. The next submit computes today
     under the new timezone and finds last_active_local_date sitting in
     what looks like the future -- satisfying neither the ==today (already
     counted) nor ==today-1 (consecutive) branch in attempts/service.py's
     streak transition -- so the streak silently RESET to 1 even though
     the user did not miss a day. Fix:
     jobs/streak_recon.py::reconcile_streak_for_timezone_change, called
     from update_me BEFORE the timezone is reassigned, compares the new
     timezone's "today" against the current stats row; if it would move
     backward past an already-counted day, clamps last_active_local_date
     down to the new "today" (the user genuinely was active "today" under
     the new clock too) and writes a streak_events row with
     event='repaired' -- the schema already reserved that value for
     exactly this. current_streak itself is never touched by a repair,
     only the date bookkeeping. An EASTWARD change is left alone: it only
     ever advances the local date, which the existing extend/reset day-math
     already handles correctly, and docs/05 only promises the boundary
     never moves backward. All existing M4 streak tests held the timezone
     fixed, which is exactly why this shipped unimplemented; new
     backend/tests/test_m7_streak_recon.py covers the westward repair
     (unit-level and end-to-end through PATCH /me + a real subsequent
     submit proving the streak survives at 5, not reset to 1), the
     eastward no-op, the no-prior-activity no-op, and the same-timezone
     no-op. Cost: one extra user_stats read on every PATCH /me timezone
     change only (not on every request); negligible.

D-69 M7 partition-cron self-recovery. Two bugs from docs/04's own warning
     ("move [attempts_default rows] out BEFORE creating the overlapping
     monthly partition or the create fails"), both closed in
     jobs/partitions.py: (a) the job only ever created NEXT month's
     partition, so a gap of two+ missed months could never close -- every
     run only ever tried the one month after "now", permanently skipping
     the months in between; (b) count_attempts_default_rows existed but
     nothing acted on it -- a CREATE TABLE ... PARTITION OF for a month
     that already has rows sitting in attempts_default fails outright, so
     once a gap opened, every subsequent run raised instead of recovering.
     Fix: ensure_next_month_attempts_partition now walks every month from
     the last existing partition (detected via pg_class name matching, not
     pg_inherits bound-parsing) through next month, closing a gap of any
     size in one run (capped at 72 months, a runaway-loop backstop, not a
     real limit). For each target month it checks for overlapping
     attempts_default rows first; if none, the original cheap direct
     CREATE TABLE ... PARTITION OF path is unchanged. If rows exist, it
     logs loudly (attempts_default_has_rows, ALERT-worthy per docs/04 --
     steady state is zero rows) and drains them: CREATE TABLE ... (LIKE
     attempts INCLUDING ALL), move the rows (DELETE ... RETURNING + INSERT
     ... OVERRIDING SYSTEM VALUE, both real bind parameters), then ALTER
     TABLE attempts ATTACH PARTITION (a plain string-interpolated DDL
     bound, like the original code, since Postgres DDL does not accept
     query parameters for partition-bound literals; both dates are always
     _first_day_of_next_month's own arithmetic, never external input).
     backend/tests/test_m7_partition_recovery.py seeds a row directly into
     attempts_default for a month with no partition (simulating a missed
     month via real Postgres partition routing, not a mock), runs the job,
     and asserts full recovery: the gap month plus every month through
     next month all get created, the stray row is drained out of
     attempts_default and provably still present (not lost) via the parent
     attempts table afterward. Cost: none identified -- the common case
     (no gap) is exactly as cheap as before.

D-70 backend/app/config.py's ANTHROPIC_API_KEY drops its Field(...,
     min_length=1) requirement (mirrors PipelineSettings, D-44) -- this
     project is OpenAI-only (D-43/D-44), and requiring a
     nonexistent-in-practice Anthropic key blocked Settings() from even
     constructing on a deploy with none set. The provider actually
     selected validates its own key lazily at first use in
     attempts/grader_client.py, as already documented for the pipeline
     side. Separately, GRADER_PROVIDER's default flips from "anthropic" to
     "openai" in both config.py and the tracked docker-compose.yml -- the
     previous default meant an un-overridden deploy would silently try
     Anthropic with an empty key and strand every summarize attempt in
     grading_pending forever (exactly the D-43 incident, just moved from
     "wrong placeholder key" to "wrong provider entirely" as the proximate
     cause). docker-compose.override.yml (gitignored, carries the real
     OPENAI_API_KEY) is unaffected; this only changes the TRACKED defaults
     so they're coherent without the override present. Cost: none
     identified -- purely a default-value fix; D-43's
     GRADER_PROVIDER=openai override becomes redundant but harmless (an
     override matching the new default is a no-op).

D-71 M7's grader-harshness investigation (CLAUDE.md M7 scope item 8: "the
     summarize grader scored 0% on a plausible answer against a seed
     rubric... only change the grader prompt if the grader is genuinely at
     fault"). Probed the real deployed path (GRADER_PROVIDER=openai,
     GRADER_MODEL=gpt-4o-mini, the real local dev key) directly against
     grade_rubric() with 8 distinct plausible-to-adversarial answers across
     all three hand-authored seed exercises (retry-with-backoff, TTL
     cache, circuit breaker) from scripts/seed_summarize_exercises.py,
     including answers deliberately worded to sound close to each
     rubric's must_not_claim phrases without actually asserting them (the
     "retries forever"/"LRU eviction" adjacent phrasings), to specifically
     stress-test the all-or-nothing scoring rule in
     rubric.py::_score_from_response (any detected must_not_claim
     violation zeros the WHOLE score regardless of must_mention hits).
     RESULT: no case scored 0%. Well-formed answers scored 1.0 across all
     three exercises; genuinely vague/terse answers (missing specific
     mechanics like "exponential" or the exact reset-timing behavior)
     scored partial credit (0.3) proportional to what they actually left
     out, correctly landing below the 0.6 pass threshold -- not zeroed. No
     adversarially-phrased-but-correct answer ever false-triggered a
     must_not_claim violation. CONCLUSION: the grader prompt is not
     systematically harsh and the seed rubrics are reasonably scoped; no
     evidence of a genuine fault on either side was found, so per the
     explicit instruction neither was changed. The originally-observed "0%"
     was most likely either an actually-deficient manual test answer, or a
     pre-D-43-era artifact (a placeholder ANTHROPIC_API_KEY making every
     real grading call error out into grading_pending/grading_failed,
     which is a different status than a scored 0.0 and could easily be
     misremembered as "scored 0%" in the moment). Cost: none -- no code
     changed; the probe scripts were throwaway and are not part of the
     tracked codebase.

D-72 M7 frontend polish, both skills/anti-slop-frontend and
     skills/ui-ux-promax consulted per docs/08's mandatory workflow even
     though this is polish, not new UI. (a) "1 days" pluralization:
     frontend/src/lib/format.ts::pluralizeDays (new, shared) fixes
     Profile.tsx's "{n} days" / "Longest: {n} days" and Reveal.tsx's
     "Streak extended/reset to {n} days" -- the hyphenated "{n}-day streak"
     phrasing elsewhere (SessionComplete, Reveal) was already correct
     English as a compound adjective and untouched. (b) Streak gutter
     ticks: docs/08/08b are explicit -- "Streak history = a column of
     gutter tick marks, not a flame emoji" -- but SessionComplete.tsx and
     Reveal.tsx's StreakLine both rendered exactly one hardcoded
     <GutterTick filled />, a single dot regardless of streak length; only
     Profile.tsx already rendered a real (if row-wrapping, not strictly
     vertical) set of ticks. New StreakTicks component in
     components/gutter/Gutter.tsx (the canonical primitive-holder file per
     its own header comment) renders a true vertical column (flex-col) of
     one filled tick per streak day, capped at 30 visible (+N earlier
     label) so an arbitrarily long streak can't render an unbounded column
     of DOM nodes -- a real latent scalability gap in the pre-existing
     Profile.tsx implementation, fixed as part of touching the same logic,
     not scope creep. All three call sites (Profile, SessionComplete,
     Reveal's StreakLine) now share this one component. Cost: none
     identified; node ./node_modules/typescript/bin/tsc --noEmit clean.

D-73 M7 adds GET /admin/metrics (app/admin/router.py, app/admin/service.py)
     mounted OUTSIDE /v1 -- not under the public API contract -- reporting
     the four golden signals from docs/02 in minimal form: session-fetch
     p95 and attempt-insert error rate (Redis counters recorded in
     sessions/router.py and attempts/router.py via the new
     app/core/metrics.py), plus the two non-negotiable ones CLAUDE.md's M7
     scope names explicitly, pending_grade_count and
     dispute_rate_by_exercise (both direct DB queries -- ops-only, low-QPS,
     not the user-facing "never aggregate attempts at request time" path
     docs/04 protects). This diverges from docs/05 section 7, which
     reserves /admin/* for "a separate internal app behind its own auth,
     deliberately out of this public contract": building that separate
     app/auth system is out of M7's scope, and CLAUDE.md's M7 prompt
     explicitly offers "a /admin/metrics JSON endpoint behind auth" as an
     acceptable minimal implementation. Gated by a shared-secret header
     (X-Admin-Token, compared with hmac.compare_digest against the new
     ADMIN_METRICS_TOKEN setting) rather than a real auth system; an unset
     token disables the endpoint entirely (404, not 403 -- doesn't confirm
     the route exists) rather than defaulting open. Still passes through
     the new default rate-limit middleware (D-64) like every other route.
     Swappable for a real internal admin app later without moving the
     public /v1 contract at all. Cost: one more shared secret to provision
     and rotate (no rotation procedure needed beyond "change the env var
     and deploy" -- it's stateless, unlike TOKEN_ENC_KEY).

D-74 M8 makes a real content batch (`python -m pipeline.orchestrator --n N`)
     survive a rate limit and a crash instead of losing the whole run.
     `pipeline/llm_client.py`'s `OpenAILLMClient` now wraps every
     `chat.completions.create` call in `_create_with_rate_limit_retry`:
     `openai.RateLimitError` with `insufficient_quota` raises a new
     `OpenAIQuotaExceededError` immediately (a billing/plan problem, not a
     transient limit -- retrying can never succeed, so it must fail loud
     and distinctly, not eat the retry budget); any other `RateLimitError`
     (`rate_limit_exceeded`, an RPM/TPM cap) backs off exponentially
     (2s/4s/8s/16s/32s, capped 60s) up to 5 retries before finally raising.
     Layered underneath the existing D-47 max_tokens/temperature 400
     fallback, not replacing it. Separately, `pipeline/orchestrator.py`'s
     `run_batch` gained `commit_after_each_spec` (off by default, so the
     `db_session` test fixture's rollback-only isolation is unchanged; the
     real CLI entry point in `main()` turns it on): it commits after every
     spec is resolved (published or exhausted), so a crash later in the
     batch -- an unhandled `insufficient_quota`, a killed process -- only
     loses the one spec in flight, never the candidates already published
     before it. `pipeline/publish.py`'s `fetch_live_pool_hashes` (renamed
     `fetch_dedup_pool_hashes`) now dedupes against `status IN ('live',
     'in_review')`, not `live` only: a crashed-and-resumed batch, or simply
     running the same command again, would otherwise burn generation+gate
     cost regenerating a near-identical candidate already sitting in the
     review queue -- CLAUDE.md's "make repeated runs additive and
     idempotent" is satisfied by these three changes together rather than a
     separate `--resume` flag/checkpoint file. The exact command to run a
     batch is unchanged: `python -m pipeline.orchestrator --n 35` (repeat
     per batch of ~30-40; `--seed` optional). Cost: one extra `source`
     status in the dedup query (negligible); a killed-mid-spec run's
     in-flight candidate's LLM calls are spent and not published, same as
     before.

D-75 M8 spec sampling is coverage-driven by default (`coverage_driven_
     sampling=True` on `run_batch`), not uniform, so a 200-exercise corpus
     actually covers the taxonomy instead of clustering on whatever concept
     samples easiest. `pipeline/publish.py::concept_type_coverage` counts
     LIVE exercises per (type, concept); `pipeline/spec_sampler.py::
     sample_spec` gained an optional `concept_coverage` param -- when given,
     concept choice is `rng.choices(..., weights=[1/(1+count) for each
     concept])` instead of `rng.choice`, so a zero-coverage concept is
     weighted equally against any other zero-coverage concept and always
     outweighs anything with existing coverage, but is never sampled with
     certainty (a concept that's merely under-covered still gets picked
     sometimes, which matters once every concept has at least one). The
     orchestrator fetches coverage once per batch, then updates its
     in-memory copy after every publish (`coverage[(type, concept)] += 1`)
     so a long batch's own progress is reflected in later samples within
     the same run, not just what was live before it started.
     `BatchReport.log_summary()` logs the zero-coverage concept list (via
     `pipeline.taxonomy.concepts_for_type`, so `requires_forbidden`
     concepts per D-54 are correctly never counted as a gap) both before
     and after the batch, so "coverage before and after" is answerable from
     the batch's own log output. Cost: one extra DB query per batch (not
     per candidate); in-memory coverage tracking is a plain dict, no new
     schema.

D-76 M8 adds per-run token/cost visibility to the batch report (CLAUDE.md:
     "so I can see spend per run and per accepted exercise"). Real LLM
     clients (`OpenAILLMClient`, `AnthropicLLMClient`) now carry a
     `TokenUsage` accumulator (`prompt_tokens`/`completion_tokens`/`calls`)
     updated from each response's real `usage` field;
     `pipeline.llm_client.estimate_cost_usd(model, usage)` looks the model
     up in a small `PRICING_USD_PER_1M_TOKENS` table (currently gpt-4.1,
     gpt-4.1-mini, gpt-4o, gpt-4o-mini -- the models this project actually
     pins, D-14) and returns `None` for an unrecognized model rather than
     guessing. `run_batch` reads `generator_client.usage`/`gate_client.
     usage` after the loop (via `getattr(..., "usage", TokenUsage())`, so
     `ScriptedLLMClient` -- which also grew a zero `usage` attribute for
     interface parity -- never breaks tests that don't care about cost) and
     `BatchReport.log_summary()` logs prompt/completion tokens and
     estimated USD per role plus a total and a per-published-exercise
     figure. Cost: none identified -- purely additive; unknown-model
     batches still report token counts, just no dollar figure.

D-77 M8 makes `pipeline/review_cli.py` usable at 200-exercise review scale
     (CLAUDE.md M8 part 2). `list` now prints a `quality_summary` line per
     row (semantic gate verdicts, solver confidence, and a flags list) read
     from the exercise's on-disk validation report (D-48), computed by the
     new `quality_flags()` -- surfaces a sandbox-derived-vs-claimed bug_line
     mismatch (D-49/D-11), an explanation whose draft never referenced the
     verified facts (D-32's `mismatch_flagged`), and any gate that landed on
     `flag` instead of a clean `pass` -- so a reviewer can triage before
     opening anything. `show` (and the new `format_exercise_markdown`,
     shared with `packet`) now renders a curated view instead of raw JSON
     dumps: the code, the answer options with the correct one marked, the
     SANDBOX-VERIFIED answer key (never the generator's claim, per D-49),
     the failing-test proof for spot_the_bug / captured stdout for trace,
     the explanation, the sandbox check-by-check pass/fail list, and every
     semantic gate's verdict+detail. A new `packet` command
     (`python -m pipeline.review_cli packet [--out PATH] [--limit N]`,
     default `pipeline/review_packet.md`, limit 500) exports every pending
     exercise into ONE markdown file with a table-of-contents (each entry
     showing its quality summary) followed by every exercise's full
     section -- the only realistic way to review a 200-exercise batch in
     one sitting, per CLAUDE.md's explicit ask. `load_validation_report`
     degrades to `None` (not a crash) on a missing/unreadable report file,
     surfaced as its own `no_validation_report` flag. Nothing about
     approve/kill/fix-and-bump/pull changed; still nothing auto-publishes.
     Cost: none identified; `list`/`packet` now read one file per exercise
     off local disk, negligible at review-CLI qps.

D-78 M8 beta allowlist. Migration `0002_beta_allowlist` (`db/schema.sql`
     updated to match, per M1's own precedent) adds `users.beta_allowed
     boolean NOT NULL DEFAULT false` and a new `beta_invites (github_login
     citext PRIMARY KEY, note, created_at)` table -- a citext PK so an
     admin can invite a GitHub handle BEFORE that person has ever logged in
     (no user row exists yet to flip a column on). `auth/service.py::
     upsert_github_user` now calls `_apply_beta_invite` in both its
     existing-identity and new-user branches (refactored to one exit path):
     if the login matches a `beta_invites` row, `beta_allowed` flips to
     true; it is never flipped false by login itself, only by the explicit
     `revoke_beta_access` admin action. `auth/router.py::github_callback`
     checks `user.beta_allowed` right after `upsert_github_user` returns:
     if false, the user row is still committed (so a not-yet-invited signup
     attempt leaves a row an admin can grant access to by username, with no
     second login required) but no refresh token is issued and the redirect
     carries `error=beta_required` instead of landing in the app.
     `auth/service.py::rotate_refresh_token` also checks `user.beta_allowed`
     (right after loading `user`, before rotating) and 401s exactly like an
     invalid token if it is false -- this is what makes a MID-beta revoke
     actually take effect: a revoked user's existing access token still
     works for its remaining `ACCESS_TOKEN_TTL` (15 min), but their next
     refresh is rejected and they are effectively logged out. Two new
     service functions, `invite_to_beta`/`revoke_beta_access`
     (`auth/service.py`), are the admin path: idempotent
     (`ON CONFLICT DO NOTHING` via `already_invited`/re-checking before
     insert), each committing its own transaction (same pattern as
     `pull_exercise`, D-58 -- a standalone admin action, not a step in a
     larger one), and each immediately flipping an already-existing user's
     `beta_allowed` if a matching username exists rather than waiting for
     their next login. Exposed as `POST /admin/beta/invite` and
     `POST /admin/beta/revoke` (`{"github_login": "..."}`,
     `app/schemas/admin.py::BetaInviteRequest`), gated by the same
     `X-Admin-Token` shared secret as `/admin/metrics` (D-73) -- no new
     secret introduced. Cost: one migration; one extra `beta_invites`
     lookup per login (new-user or returning); a revoked user is not force-
     logged-out instantly, only within one `ACCESS_TOKEN_TTL` window (15
     min) -- acceptable for a beta-scale incident response, documented here
     rather than adding per-request DB checks to every authenticated route.

D-79 M8 beta-week observability, all folded into the existing `GET
     /admin/metrics` (D-73) rather than new standalone endpoints, except
     retention which gets its own (a query, not a point-in-time gauge).
     (a) `empty_session_rate`: `sessions/service.py::
     _build_and_persist_session` now calls `core.metrics.record_outcome`
     with `is_error=True` when `build_session_slots` returns empty (the
     D-59 transient-empty-day path) and `is_error=False` otherwise -- the
     only place a session build is actually attempted -- surfaced via the
     existing `error_rate()` helper, so "empty-session occurrences" (one of
     the things CLAUDE.md's M8 prompt asks to watch) is a real number, not
     a TODO. (b) `jobs`: `app/jobs/runner.py::JobScheduler` gained
     `last_run_at`/`last_error_at` (ISO timestamps, alongside the existing
     `run_counts`/`error_counts`) because a cumulative count alone can't
     answer "is grading_retry still ticking right now" between two polls;
     `admin/service.py::job_health()` shapes this per job name, and is
     `None` (not `{}`) when `JOBS_ENABLED=false`, so a disabled scheduler
     reads distinctly from a healthy one with nothing to report yet.
     (c) `GET /admin/retention?cohort_start=YYYY-MM-DD&offset_days=1|7`
     (`admin/service.py::compute_retention`) answers D1/D7 directly: of the
     users with a `daily_sessions` row on `cohort_start` (a session was
     fetched/built that day -- build-on-request, D-23, so this row existing
     IS "they opened the app"), what fraction have one on
     `cohort_start + offset_days` too. Same `X-Admin-Token` gate as every
     other admin route; no new secret. Combined with the already-existing
     `pending_grade_count`/`dispute_rate_by_exercise` (D-73) and
     `attempt_insert_error_rate`, the full beta-week watch list from
     CLAUDE.md's M8 part 3 question 8 is now: pending_grade_count (grader
     health), dispute_rate_by_exercise (bad answer keys), attempt_insert_
     error_rate (submit path health), empty_session_rate (content pool
     health), jobs.*.last_run_at/last_error_at (background job health), and
     GET /admin/retention (did people come back) -- every one of them a
     real, queried number, none a manual eyeball check. Cost: one extra
     Redis counter pair (session_build) recorded on every session-build
     attempt, negligible; two extra dict writes per job tick.

D-80 STB corpus fixes (from the spot_the_bug reject diagnosis) plus a new
     predict_the_fix exercise type. Five coordinated changes; none weakens
     D-49, the twin-snippet invariant, or any gate.
     (a) TAXONOMY -- omission / no-divergence concepts flagged unsamplable FOR
     spot_the_bug (taxonomy.Concept.stb_unsamplable, per-type, distinct from
     D-54's global requires_forbidden). The dominant structural STB reject is
     a concept whose canonical bug cannot yield a discriminating twin-snippet
     with a diff-derived key: either an OMISSION bug whose fix is a pure
     INSERTION (D-49 correctly rejects the empty diff -- nothing to point at),
     or a NO-DIVERGENCE bug where buggy and fixed produce identical output so
     no test can fail on one and pass on the other. Same class as D-54 (the
     gate is right, the concept/type pairing is wrong). Audited the whole
     taxonomy; flagged five: decorator-losing-metadata (INSERTS @wraps, 3/3
     deterministic reject), idempotency-missing (INSERTS a guard, 3/3),
     concurrency-conceptual (no real threads -> the race never triggers
     deterministically, and the fix is an inserted lock), exception-type-too-
     broad (narrowing an over-broad except ADDS a handler/re-raise; confirmed
     reject), and n-plus-one-pattern (batching changes only a query COUNT, not
     the returned value -- no output divergence, and the fix is a whole-loop
     restructure). Per-type, not global, precisely because most stay valid for
     trace: exception-type-too-broad (the only _BOTH member of the five) keeps
     its trace samplability; the other four are _STB_ONLY, so flagging removes
     them entirely. concepts_for_type excludes stb_unsamplable only for
     exercise_type == 'spot_the_bug'; predict_the_fix inherits the exclusion
     transitively (it is derived from verified STB candidates, never sampled).
     get_concept still resolves flagged slugs, so already-published exercises
     keep resolving; clearing the field re-enables a concept if a dodging
     realization is ever found. Each doomed spec previously burned up to
     MAX_ATTEMPTS_PER_SPEC = 3 full generate+gate rounds.
     (b) LINE BUDGET now MAX-ONLY for buggy_code and trace code (static_gate.
     check accepts line_budget=(None, hi); orchestrator._static_gate_check
     passes (None, line_budget_max)). Evidence, not analogy: every budget
     reject in the persisted reject reports (D-48) was code UNDER the min --
     a minimal clear bug is naturally 5-8 lines at difficulty 1-2, and neither
     the STB nor the trace model can pad to 40-60 at difficulty 9-10 -- except
     TWO STB cases over the max, which keeping the max still catches. Trace was
     100% under-min, zero over-max, so the same max-only rule applies to it on
     its own evidence. The min was a readability nicety, not a correctness
     rule; the max protects against an unreadably long snippet and stays. The
     stb_py_v3 length line is softened to match (max hard, min a soft aim).
     (c) stb_py_v3 (prompt_template_id stb_py_v3; generate.py points at it,
     replacing v2 per the README versioning contract, v2 kept on disk). The
     dominant CONTENT reject (13 of 55) was a test that does not discriminate:
     a real bug is planted, then test inputs are chosen where buggy and fixed
     produce IDENTICAL output, so the assertion never fires and buggy+test
     exits 0 (which fails the sandbox gate's buggy_fails_test check). v2 taught
     insertion+replace and exception-to-assertion by worked example but nothing
     about input selection; abstract rules do not land with this model, worked
     examples do (the standing finding behind D-46/D-53). v3's constraint 11
     adds a complete buggy/fixed/test/bug_lines triple demonstrating choosing
     the divergence-boundary input (an off-by-one threshold tested at exactly
     the boundary, with the explicit rule "if your buggy and fixed code agree
     on your chosen input, the test is worthless and the exercise is invalid").
     A new optional self_check field (test_input_is_on_the_divergence_boundary)
     nudges compliance; STBSelfCheck made it optional so v2 output and every
     existing fixture still validate. The gate is NOT relaxed -- buggy_fails_
     test already rejects a non-discriminating test; the prompt now teaches the
     property the gate enforces.
     (d) PER-TYPE GENERATOR MODEL ROUTING built but OFF by default
     (GENERATOR_MODEL_STB, empty = use GENERATOR_MODEL for STB too). When set
     (and different from GENERATOR_MODEL), run_batch routes ONLY spot_the_bug
     generation to it via stb_generator_client; trace and the predict_the_fix
     distractor step stay on the base generator. STB is the flagship and the
     only type worth a premium model. assert_gate_and_generator_models_differ
     also guards GENERATOR_MODEL_STB != GATE_MODEL (D-14). One env var flips it
     on; the diagnosis quantified STB-only routing to gpt-5.5 at ~$18-53 to
     seed all 35 STB concepts. Measure the free fixes (a/b/c) first.
     (e) predict_the_fix -- a new deterministic (choice-graded) exercise type
     derived from a sandbox-verified spot_the_bug, nearly free because it
     reuses artifacts already proven by execution. Every verified STB candidate
     has a (buggy, fixed, test) triple proven to fail-on-buggy/pass-on-fixed;
     that IS a predict_the_fix: payload = buggy code + the failing test and its
     captured output, question "which change makes the test pass?", correct
     choice = the execution-proven fixed_code (never an LLM claim). The
     generator (ptf_py_v1) is asked ONLY for 3 wrong-fix distractors; the NEW
     GATE INVARIANT (sandbox_gate.validate_predict_the_fix) executes each
     distractor against the same test and REQUIRES it to STILL FAIL with
     AssertionError -- a distractor that passes is not wrong (a second correct
     answer) and rejects the candidate; one that fails with a non-AssertionError
     is broken code, not a plausible fix, and also rejects; distractors must be
     textually distinct from buggy_code, fixed_code, and each other; double-run
     determinism throughout. Grading is deterministic (choice_id), same as
     trace, so ZERO per-answer LLM cost. Wiring: pipeline gets PredictFixCandidate
     (schemas), predict_the_fix.py (generate + assemble), validate_predict_the_
     fix (gate), orchestrator._derive_and_publish_ptf (fires after a published
     has_bug STB survivor; derive_predict_the_fix flag, ON for real batches via
     main(), OFF in run_batch's default so existing tests -- whose scripted
     clients queue only primary-path responses -- are untouched), and
     publish.insert_predict_the_fix (source.derived_from records the parent
     STB). A PTF failure never unpublishes its STB. Backend: migration
     0003_predict_the_fix_type widens the exercises.type CHECK (+ db/schema.sql
     and the SQLAlchemy CheckConstraint); grading.py, schemas/attempts.py
     (PredictTheFixReveal), schemas/session.py (+ failing_test/test_output
     payload fields), sessions/service.py serialization, and the session
     sampler's DETERMINISTIC_TYPES all gain the type. Frontend: lib/types.ts,
     PredictTheFixAnswer.tsx (choice list of code diffs), Session.tsx dispatch,
     Reveal.tsx view. predict_the_fix is not run through the AST-dedup gate --
     it derives from an already-deduped STB, so it is unique by construction;
     its source.content_hash is a plain sha256 over buggy+wrong-fix codes,
     distinct from the parent STB's buggy-only hash so the two never collide.
     Cost: one extra generator call + a sandbox pass per STB survivor (both
     reusing verified artifacts), and one migration; the answer key is
     execution-proven, never an LLM judgment, so invariant 1 holds. The
     measuring batch: python -m pipeline.orchestrator --n 35 (--seed optional)
     produces both STB (via v3, free fixes a/b/c) and the derived
     predict_the_fix, and logs survival per stage.

D-81 Pipeline defect #5: `defect_audit` was a broken judge. The spot_the_bug
     reject diagnosis of the latest run found the semantic gate was the SECOND
     largest STB killer (14 of 48 rejects) and that ~11 of those 14 were FALSE
     rejects of execution-verified, single-bug content. Root cause was the gate
     model (gpt-4o-mini): given un-numbered code, it identified the ONE real bug
     correctly and then reported it at the WRONG line number (verified line 25
     reported as 20, line 45 as 30 -- the undercount grows with depth, the
     signature of a model counting lines it cannot count), which the orchestrator
     then killed with an exact `set(defects[0].lines) & set(bug_lines)`
     intersection; and it listed the exact "hypothetical improvements" its own
     prompt forbids (normal slicing behavior, "allows duplicates", a
     `metadata or {}` nit), inflating the count past the exactly-one rule. This
     is the inverse of the twin-snippet trap: a WEAK gate wearing a model-ceiling
     costume. Four fixes, none weakening a gate:
     (A1) `semantic_gates._number_lines` prefixes every line fed to defect_audit,
     solver, and reasons with its 1-indexed number (via splitlines(), so line N
     matches the sandbox's diff-derived verified_bug_lines); the prompts tell the
     model to report the number it READS, not one it counts. This removes the
     counting step that caused the mis-numbering.
     (A2) defect_audit's decision rule matches the single reported defect against
     the verified bug region with a +/-2-line window (`_defect_lines_match_bug_
     region`) instead of a brittle exact intersection -- defense in depth for a
     construct-spanning bug attributed to the def line or one line off. The
     "exactly one defect" count is UNCHANGED (still the trust product, D-13); the
     window is tight (2) so a genuine second bug in another function -- always
     many lines away -- still rejects.
     (A4) the defect_audit prompt's anti-nit instruction is rewritten from a
     one-line "do not list ... hypothetical improvements" (which gpt-4o-mini
     ignored) into a hard rule with concrete NON-defects (correct-but-surprising
     behavior, a missing feature/validation never asked for, a style preference,
     the same bug re-described per method) plus "prefer fewer, higher-confidence
     defects".
     (A3) GATE_MODEL moves off gpt-4o-mini. Recommended default gpt-4o (.env.
     example, backend/.env.example): stronger at instruction-following AND a
     gpt-4* family, so it still honors the gates' designed temperature=0 (a
     deterministic judge). A gpt-5* model is smarter still but CANNOT honor a
     non-default temperature (D-55 already resolves that up front and warns), so
     it is documented as an alternative, not the default -- a non-deterministic
     judge is the wrong trade for a fairness gate. Pricing table gains gpt-5-mini/
     gpt-5 so cost still reports if chosen. The gate model was already fully
     wired for gpt-5* via D-47/D-55; no client change was needed.
     Proof (offline, no batch): new test_m3_semantic_gates fixtures built from
     this run's real false rejects -- a defect reported ON the numbered key line
     PASSES, a defect reported within the +/-2 window PASSES (the old exact match
     rejected it), a defect far from the region still REJECTS, and a genuine
     two-bug candidate still REJECTS. gpt-5* temperature handling is covered by
     the existing test_m3_llm_client suite.

D-82 STB generator redesign, stb_py_v4 (new file; v1-v3 retired but kept per the
     README versioning contract; generate.py points at v4). The dominant STB
     SANDBOX reject is buggy_fails_test -- a real bug is planted but the test does
     not discriminate (buggy+test exits 0). v3's single divergence-boundary
     worked example (D-80) did NOT move it: buggy_fails_test as a share of STB
     sandbox rejects went 59% -> 64% -> 71% across the last three runs. Published
     rationale (SymPrompt arXiv 2402.00097 improved correct test generation ~5x
     by deconstructing generation into stages aligned with the method's execution
     paths; CoSPlay arXiv 2605.23491: one-shot test prompting yields tests "not
     grounded in the way code candidates may fail") says the fix is decomposition
     forced as machine-checkable output, not another abstract rule. v4:
     (B1) write the CORRECT code FIRST, then plant exactly one bug -> buggy_code
     (v3 wrote buggy-first and back-filled a fix; 4 of this run's sandbox rejects
     were fixed_passes_test failures from that).
     (B2) DERIVE the divergence as five new REQUIRED fields (bug_trigger_
     condition, divergence_input, buggy_result_on_divergence_input, fixed_result_
     on_divergence_input, divergence_justification). The test must assert on
     divergence_input.
     (B3) a FREE static check (schemas.STBCandidate model_validator): if the
     model's own buggy_result == fixed_result on its chosen input, it has ADMITTED
     the test cannot discriminate -> rejected at SCHEMA VALIDATION, zero tokens,
     zero sandbox, before the 6-container pass. Fields are all-or-none; has_bug=
     false omits all five. Optional on the schema so v2/v3 output and every
     existing fixture still validate.
     (B4) the D-11 claim-check pattern, now for STB (the key structural addition;
     trace has always had it, STB never did). The v4 test PRINTS repr(result)
     before asserting, so the buggy+test and fixed+test runs the sandbox already
     makes capture the ACTUAL results on stdout -- ZERO extra runs. sandbox_gate
     check `stb_claim_matches_execution` compares them to the model's claimed
     buggy/fixed results and REJECTS on mismatch: a model that mis-predicts its
     own code wrote an unreliable exercise, exactly as trace's captured_output_
     matches_claim rejects. Skipped for v2/v3 candidates and has_bug=false (no
     divergence fields), so it can never false-reject older content.
     (B5) three worked examples of STRUCTURALLY different divergence patterns
     (boundary value; empty/degenerate collection; cross-call state leakage --
     the mutable-default family a single-call test can never catch), each showing
     the full chain correct-code -> planted bug -> trigger -> input -> both
     results -> the printing/asserting test. v3's lone numeric-threshold example
     invited over-fitting to that one shape.
     (B6) a self-review self_check field (test_asserts_on_divergence_input),
     untrusted like the rest of self_check; the B4 claim-check is the real
     enforcement.
     No gate or invariant is weakened: B3/B4 ADD checks; invariant 1 holds (the
     answer key stays execution-derived, D-49). Proof (offline, no batch):
     test_m3_sandbox gains B3 schema tests (identical results reject for free;
     partial fields reject; no-divergence candidates still validate) and B4
     sandbox tests (a correct prediction accepts; a mispredicted result rejects
     on stb_claim_matches_execution). test_m3_pipeline pins template_id stb_py_v4
     and the print(repr(result)) contract. The measuring batch is unchanged:
     python -m pipeline.orchestrator --n 35 (--seed optional).

D-83 Feedback-driven REPAIR replaces blind regeneration for the repairable
     subset of rejections, grounded in the generation-verification pattern
     (ReVeal, arXiv 2506.11442): on rejection the candidate is fed BACK to the
     generator with the specific failed check and its concrete evidence (the
     reject report D-48 already captured and used to throw away) and asked for a
     TARGETED fix, instead of rolling three independent dice on the same spec.
     This SUPERSEDES D-10 ("gates never repair") for repairable rejections only;
     D-10's reasoning (repaired candidates inherit inconsistencies) is answered
     structurally -- a repaired candidate is NOT trusted: it goes through the
     FULL gate chain again with zero exemptions, so invariant 1 is untouched and
     nothing publishes without execution proof. The classification taxonomy is
     the heart of the change and is encoded in pipeline/repair.py:
       REPAIRABLE (the bug and the code are fine; one artifact is wrong):
         - static_gate: a forbidden import/call, a hint word, over budget --
           mechanical; the exercise idea survives.
         - buggy_fails_test (sandbox): the test passed on the buggy code. The
           planted bug is real; the input just isn't on the divergence boundary.
           Repair asks for a new divergence_input + test, buggy/fixed UNCHANGED.
         - fixed_passes_test (sandbox): the fix isn't self-consistent with the test.
         - stb_claim_matches_execution (sandbox B4): the model mispredicted its
           own results; repair is handed the ACTUAL captured outputs.
         - captured_output_matches_claim (trace sandbox): the model mis-traced
           its own code; repair is handed the REAL captured stdout.
       FUNDAMENTAL (the exercise IDEA is bad; regenerate fresh, NEVER repair):
         - defect_audit found a genuine SECOND defect (the code does too much).
         - solver couldn't solve it / flagged it ambiguous (a semantic REJECT).
         - reasons flagged a distractor partially_defensible, or the reason
           options are mis-keyed (D-13).
         - dedup: a duplicate -- a repair cannot make it non-duplicate.
       A sandbox rejection is REPAIRABLE only if EVERY failing check is on the
       repairable list; a single fundamental failure alongside (e.g.
       deterministic_double_run, fix_diff_real_and_minimal, buggy_runs_clean)
       makes the whole candidate fundamental. Repairing a fundamental failure is
       asking the model to rescue a bad idea; the attempt is spent on a fresh
       candidate instead.
     HARD BOUNDS (this is what stops it becoming a money pit):
       - at most MAX_REPAIR_ROUNDS = 2 repairs per candidate lineage;
       - if the SAME check fails again after a repair, that lineage stops
         repairing (it can't get there);
       - repairs draw from the SAME MAX_ATTEMPTS_PER_SPEC budget as fresh
         generations (raised to 4 for the real batch), so total LLM generation
         calls per spec are capped regardless of how repair/best-of-N interleave;
       - a repair prompt is repair_stb_v1 / repair_trace_v1: change ONLY what the
         named failure requires, preserve the bug/concept/code, re-emit the same
         schema; a JSON-parse failure gets the same single retry as generation.
     INSTRUMENTATION (so we can tell if it pays for itself, not discover later):
       repair_attempted/succeeded/failed broken down by triggering check;
       published_via_repair vs published_first_try; repair_stopped_{same_check,
       max_rounds,budget}; and the MARGINAL repair token cost (the extra
       generation calls + the extra gate passes re-validating repaired
       candidates, attributed by snapshotting client usage deltas), priced with
       the right model each and reported as per_rescued_usd. OFF by default in
       run_batch (LoopPolicy defaults) so every existing test whose scripted
       client queues exactly the primary-path responses is unchanged; the real
       batch CLI turns it on from PipelineSettings.REPAIR_ENABLED. Proof
       (offline, mocked LLM, real Docker sandbox): test_m8_pipeline_upgrades --
       a non-discriminating STB triggers a buggy_fails_test repair whose evidence
       and original candidate ride in the prompt and whose discriminating fix
       publishes; a second-defect reject never repairs; a same-check-twice
       lineage stops; the budget caps total calls (cannot loop forever); and the
       repaired candidate provably runs the full sandbox + 3 semantic gate calls.
       Cost: the orchestrator's per-spec loop is decomposed
       (evaluate -> lineage -> best-of-N -> publish); the dedup-pool add moved to
       publish time (a candidate's hash is added only when it actually ships, so
       best-of-N siblings don't dedup against each other).

D-84 BEST-OF-N selection: a spec no longer publishes the FIRST candidate that
     clears the gates (arrival order is not a quality metric); where budget
     allows it produces multiple SURVIVORS and publishes the highest-scoring.
     The quality score (pipeline/scoring.py) is computed from signals the gate
     chain ALREADY collects for free -- no extra LLM call:
       - solver confidence vs authored difficulty (the strongest free signal):
         a hard-authored exercise the gate model solved instantly at high
         confidence is boring or mislabeled (penalty); genuine struggle (lower
         confidence, still correct) on a high-difficulty spec is a QUALITY
         MARKER (bonus);
       - penalties: a bug visible in the first two lines, trivially short code at
         high difficulty, a bug_lines/B4 claim mismatch, or surviving only with a
         human-review FLAG.
     Two uses (2b): select the best survivor when there is more than one; and
     CALIBRATE difficulty at generation time -- a hard-authored exercise the
     solver breezed is flagged difficulty_miscalibrated for downgrade/review,
     closing the gap D-61 leaves before launch (difficulty_empirical needs 30
     graded attempts we don't have yet). Cost control (2c): extra survivors are
     pursued ONLY when the best so far scores below BEST_OF_N_SCORE_THRESHOLD
     (0.70) OR the concept is under-covered (< BEST_OF_N_COVERAGE_THRESHOLD live
     exercises), capped at BEST_OF_N_MAX_SURVIVORS = 2 -- never a blanket triple.
     Every threshold is an explicit, tunable setting. OFF by default in run_batch;
     the real batch turns it on (PipelineSettings.BEST_OF_N_ENABLED). Proof
     (offline): two survivors clear every gate, one with its bug on line 2 (a
     scoring penalty) and one on line 4; best-of-N publishes the higher-scoring
     line-4 one, and the pure scorer tests pin the breezed-hard penalty, the
     struggle bonus, and the early-bug penalty. Cost: a spec that scores its
     first survivor poorly (or hits an under-covered concept) spends up to one
     extra lineage; bounded by the same MAX_ATTEMPTS_PER_SPEC budget as repair.

D-85 PROMPT-CACHING plumbing (the measurement + pricing half of the caching
     upgrade; the prompt restructure that makes it engage is D-86). OpenAI prompt
     caching is automatic on the message-array prefix; to realize and MEASURE it:
     (a) OpenAILLMClient captures usage.prompt_tokens_details.cached_tokens into a
     new TokenUsage.cached_prompt_tokens (a SUBSET of prompt_tokens, never
     additive); (b) it sends a stable prompt_cache_key derived from the (spec-
     independent) system prompt so cache routing is consistent under concurrency,
     with a defensive drop-and-retry if an older SDK/model rejects the kwarg
     (caching just doesn't engage, never an error); (c) estimate_cost_usd splits
     prompt tokens into fresh vs cache-hit and prices the cached portion at a new
     CACHED_INPUT_USD_PER_1M_TOKENS table (gpt-4.1 $0.50 vs $2.00 input, i.e. 75%
     off; gpt-4o $1.25 vs $2.50, 50% off; an unlisted model conservatively pays
     full price); (d) BatchReport logs cached_fraction and estimated_saved_usd per
     generator role. TokenUsage.delta_since powers the D-83 marginal-repair
     accounting too. Proof (offline): estimate_cost prices a 90%-cached prompt
     below the same prompt uncached; the delta isolates marginal spend. Cost:
     the cost table now also decays on cached-price moves; corrected in place.

D-86 The v4 spot_the_bug template (213k prompt tokens resent verbatim last batch)
     is restructured into v5 (stb_py_v5), and trace v1 into v2 (trace_py_v2), so
     the large static content becomes a spec-INDEPENDENT prefix OpenAI's prompt
     cache (D-85) serves on every call, billing only the varying spec fresh. The
     ONLY changes: the "## Specification" block (the sole varying part) is moved
     from the top of the user message to the very END, and the three (v5) / two
     (v2) inline references to the per-spec domain/concept in the body are
     genericized to point at the Specification below; {{python_version}} is a
     pinned constant (3.12) so it stays inline without breaking the prefix. All
     instructional content -- the difficulty scale, the disciplined order, the
     three worked examples, every constraint, the output schema, the distractor
     rule -- is byte-identical to v4/v1; this is a caching change, not a
     generation-logic change (v4's decomposition, the free B3 schema check, and
     the B4 execution claim-check are unchanged). Any template edit bumps the
     version per prompts/README, so v4/v1 stay on disk for traceability and
     generate.py points at v5/v2. Proof (offline): test_m8_pipeline_upgrades
     renders two very different specs and asserts the pre-Specification prefix is
     byte-identical, carries the worked examples, and exceeds 2k chars, with the
     spec at the end; test_m3_pipeline pins template_id stb_py_v5 / trace_py_v2.
     The measured cache HIT RATE and before/after prompt-token cost cannot be
     produced offline (they need a real OpenAI call), so the measuring batch
     (below) is the confirmation; the expected saving is bounded by the cached
     fraction (~the static prefix / total prompt, i.e. the large majority of the
     213k) times the model's cached discount. The one thing the batch must also
     confirm is that relocating the spec did not move generation quality -- the
     tokens are identical, so this is expected, but it is the reason the change
     is version-bumped and batch-verified rather than assumed.

     Measuring batch for D-83..D-86 (spends real tokens; run when ready):
       python -m pipeline.orchestrator --n 40 --seed 7
     It turns repair + best-of-N on from settings, derives predict_the_fix, and
     commits per spec. Read the summary lines: "orchestrator repair ..."
     (published_via_repair vs first_try, per_rescued_usd), "orchestrator cache
     ..." (cached_fraction, estimated_saved_usd), and "orchestrator cost ..."
     (per_published_usd). Repair is NOT paying for itself if per_rescued_usd
     exceeds the fresh cost-per-published, or if repair_failed dwarfs
     repair_succeeded on a given check (that check should move back to
     FUNDAMENTAL). Expected after this change, on this gate design (D-56's
     ~20-30% first-try survival): publish-rate per spec up (repair rescues the
     buggy_fails_test / static rejects that were the biggest wasted spend, and
     best-of-N spends only where quality is low), and cost-per-published DOWN
     (caching removes the dominant prompt-token cost; repair is cheaper than a
     fresh candidate in expectation because it reuses a mostly-correct one).

D-87 File-provider content ingestion (`pipeline/ingest.py`, `python -m
     pipeline.ingest --file <path>`): a way to run HAND-AUTHORED candidates
     through the exact same, unmodified gate chain as LLM-generated ones,
     because invariant 1 (no LLM claim is ever ground truth) does not carve
     out an exception for candidates a human typed -- a hand-authored
     `buggy_fails_test` claim is exactly as untrusted as a generated one until
     the sandbox proves it. Reuses orchestrator internals verbatim
     (`_evaluate_candidate`, `_publish_survivor`, `_record_reject`,
     `BatchReport`) rather than re-implementing any gate logic, so the two
     paths cannot silently diverge. Three deliberate differences from a
     sampled batch, all because there is no generator in this path -- a human
     already committed to exactly one candidate per spec:
       (a) NO REPAIR, NO REGENERATION. D-83's repair loop and D-84's best-of-N
       both assume a generator that can be asked to try again; ingest calls
       `_evaluate_candidate` directly (bucket="first_try"), never
       `_run_lineage`. A gate rejection is terminal and gets the same D-48
       reject report as any other -- "if one fails a gate, it fails."
       (b) `spec_sampler.line_budget_for_difficulty` (renamed from
       `_line_budget_for_difficulty`; the one call site in `sample_spec` moved
       with it, behavior unchanged) derives `line_budget_min/max` from the
       JSON spec's `difficulty`, since a hand-authored spec has no sampler run
       to produce them. `domain` defaults to a fixed placeholder string
       (only used as flavor text in the predict_the_fix distractor prompt,
       never gate logic). `concept` is validated against
       `taxonomy.concepts_for_type("spot_the_bug")` at load time -- the same
       set the sampler itself draws from, so a flagged (`requires_forbidden`/
       `stb_unsamplable`, D-54/D-80) or misspelled concept is rejected before
       any gate runs, not discovered as a mystery reject three stages later.
       (c) B3 (D-82, the free buggy_result==fixed_result static check) is a
       `model_validator` on `schemas.STBCandidate` itself -- unconditional,
       cannot be bypassed by any caller -- so `STBCandidate.model_validate()`
       on the raw `candidate` dict is both the load step and the first gate.
       A schema/B3 failure, an unsupported `spec.type` (only spot_the_bug is
       wired; trace has no hand-authored batch yet), or a `prompt_template_id`
       other than the required tag (below) is a stage="load" rejection with
       its own D-48-style report, before static_gate is ever reached.
     PROVENANCE (three permanently distinguishable origins, per M8 content
     counts / coverage reporting): `publish.insert_candidate` gains an
     `origin: str = "llm"` parameter (default preserves every existing
     caller's behavior byte-for-byte); `orchestrator._publish_survivor` gains
     the same, threaded through. `pipeline/ingest.py` passes
     `origin="handauthored_claude"` and `template_id="handauthored_stb_v1"`
     (the latter flows into `source.prompt_template_id` via the existing
     `validation_report["template_id"]` plumbing, no publish.py change
     needed) -- distinct from orchestrator content (`source.origin="llm"`)
     and from the older hand-typed seed content (`source.origin=
     "seed_handauthored"`, D-62, which also never touched a gate). The input
     file's own `prompt_template_id` field is validated to equal
     `"handauthored_stb_v1"` exactly at load time (a provenance tag is not
     free-form input from the batch file) rather than trusted through.
     `source.model` for a hand-authored row is the literal string `"claude"`
     (`AUTHOR_LABEL`), never an LLM_client model string -- no generator call
     produced the candidate, so nothing resembling GENERATOR_MODEL applies.
     D-14 IS BINDING: `pipeline.ingest.main()` hard-fails (`RuntimeError`,
     not a log warning) if `GATE_PROVIDER != "openai"` OR
     `GENERATOR_PROVIDER != "openai"` before touching the batch file at all --
     content authored by Claude must be judged by a genuinely different model
     family, and the predict_the_fix distractor-generation step (still an LLM
     call, D-80) must not route to Anthropic either. This is stricter than
     the general-purpose `assert_gate_and_generator_models_differ()` (which
     only compares GATE_MODEL against GENERATOR_MODEL, not providers) because
     a same-provider-different-model pair is an insufficient guarantee here:
     the generator identity that actually matters for D-14 is "Claude", which
     no GENERATOR_MODEL/GATE_MODEL string comparison can see.
     PTF DERIVATION is unmodified: `_publish_survivor`'s existing
     `derive_predict_the_fix` branch runs exactly as it does for an
     orchestrator batch (D-80) -- wrong-fix distractors generated on the base
     OpenAI generator, each re-executed in the sandbox and required to still
     fail. `insert_predict_the_fix`'s `source.origin` stays `"llm"`
     unchanged (its differentiating content, the distractors, genuinely is
     LLM-generated); traceability to a hand-authored parent is via the
     existing `source.derived_from` pointer, not a second origin tag.
     NO EXEMPTION on the sandbox or the gate chain: `ingest_batch` calls
     `verify_sandbox_available()` (D-57) before processing anything, uses the
     same `fetch_dedup_pool_hashes` pool (a hand-authored candidate can
     dedup-collide with existing content same as any other), and commits
     per-item (`commit_after_each=True`) so a crash mid-batch only loses the
     one item in flight, mirroring `commit_after_each_spec` (D-74).
     Cost: none identified -- `origin`/`_publish_survivor` defaults keep
     every existing orchestrator call site byte-identical;
     `line_budget_for_difficulty`'s rename is a pure rename with its one call
     site updated in the same change.

D-88 Data-loss defect: `pytest` was destroying the shared dev/prod database.
     `backend/tests/conftest.py`'s `migrated_db` fixture (session-scoped,
     `autouse=True`) ran `DROP SCHEMA public CASCADE` + recreate + `alembic
     upgrade head` unconditionally against whatever `DATABASE_URL` resolved
     to -- and root `.env` / `backend/.env` both point `DATABASE_URL` at the
     SAME Postgres the API and pipeline use for real content, with no
     separate test database. CONFIRMED BY DIRECT REPRODUCTION during the D-87
     work session, not inferred: a plain `pytest` invocation destroyed ~37
     real generated exercises at some earlier, unwitnessed point (the
     originally-reported incident), and then a further 24 (18 `trace` + 5
     `spot_the_bug` + 1 `predict_the_fix`, all `source.origin="llm"`, sitting
     in `in_review` from a prior orchestrator batch) were destroyed a second
     time, live, while running this project's own test suite as part of
     "ruff clean, tests green." `0003_predict_the_fix_type` and
     `0000_schema_sql.py`'s own `downgrade()` were both investigated and
     ruled out as the actual mechanism (0003 only widens a CHECK constraint;
     0000's `DROP TABLE`s only run on an explicit `alembic downgrade`, which
     nothing in the normal dev/CI flow issues) -- `pytest` itself, every
     single run, was the mechanism.
     FIX mirrors D-62's `CODEREADER_ALLOW_SEED=1` pattern: a destructive
     operation must be a conscious, structurally-guarded opt-in, never
     pytest's default side effect. New `backend/tests/_db_guard.py` (pure
     URL/string logic, zero DB I/O except the one function documented below)
     plus a module-level block at the top of `conftest.py`, executed before
     pytest imports any test module or fixture:
       (a) `resolve_test_database_url()`: `TEST_DATABASE_URL` if explicitly
       set, else `derive_test_database_url()` appends `_test` to
       `app.config.get_settings().DATABASE_URL`'s database name (e.g.
       `codereader` -> `codereader_test`, idempotent if already suffixed).
       The base is read via `get_settings()`, NOT raw `os.environ` -- this
       project supplies `DATABASE_URL` through the `.env` FILE, which
       pydantic-settings parses internally and never writes back into
       `os.environ`, so an `os.environ`-only read silently fell back to a
       guessed default during development of this fix (a hardcoded
       `.../5432/...` guess, wrong port for this environment's actual
       `5433` mapping) and surfaced only as a confusing
       `InvalidPasswordError` several layers down -- exactly the kind of
       silent-wrong-default failure mode D-88 itself is about. Caught and
       fixed before landing; `test_resolve_test_database_url_never_reads_
       database_url_from_env_directly` pins the corrected contract.
       (b) `assert_disposable_test_database()`: FAIL LOUDLY
       (`DatabaseGuardError`) -- before any DB I/O -- unless the resolved
       database's name ends in `_test`, OR `CODEREADER_TEST_DB=1` is
       explicitly set (an escape hatch for a disposable DB with an unusual
       name). Pure function: cannot itself destroy anything, which is what
       lets a unit test prove "the guard fires" without a second real wipe.
       Called twice: once at module load, and again inside `migrated_db`
       itself immediately before its DROP SCHEMA, reading whatever
       `DATABASE_URL` actually resolves to at that moment -- belt and
       suspenders, independent of step (a).
       (c) `ensure_database_exists()`: `CREATE DATABASE` the resolved target
       if it does not exist yet ("created on demand," D-88 point 2) --
       connects to the `postgres` maintenance database, never drops or
       alters anything, and independently re-validates the identifier
       against a safe-charset regex before interpolating it into `CREATE
       DATABASE "..."` (identifiers cannot be bind-parameterized), so a
       malformed name fails loudly instead of reaching raw SQL verbatim.
       (d) The module-level block then overrides the `DATABASE_URL` env var
       itself (clearing `get_settings`'s `@lru_cache` immediately before and
       after), rather than threading a URL through every call site:
       `alembic/env.py`, `app/db.py`'s `create_engine()` default, and
       `app/main.py`'s lifespan all independently read
       `get_settings().DATABASE_URL`, and three test files construct a bare
       `create_engine()` of their own -- an env override makes every one of
       those transparently target the isolated database with zero
       per-call-site changes, so no path is left that can silently keep
       pointing at the real one.
     VERIFIED, not just reviewed: `backend/tests/test_m7_db_isolation_guard.py`
     unit-tests the guard (rejects a real-looking name with no flag, accepts
     a `_test`-suffixed name, accepts the flag override, rejects a
     not-exactly-`"1"` flag value), the derivation (idempotent, preserves
     host/user/password/port), the env-precedence contract (explicit
     override wins; a stale/wrong `DATABASE_URL` key in `env` is ignored in
     favor of the caller-supplied base), `ensure_database_exists` (creates,
     is idempotent on a second call, rejects an unsafe identifier via a
     SQL-injection-shaped probe string), and the REAL running session
     (`get_settings().DATABASE_URL` is asserted disposable from inside an
     actual test). Separately, end to end: a live-database row count was
     captured before and after both a single-file run and the full 342-test
     suite run and found byte-identical (unchanged) in both cases -- proof
     by direct measurement, not by trusting the code review, matching the
     rigor D-45/D-57 set for a trust-relevant fix.
     CI (`.github/workflows/ci.yml`, `pytest` job): the `pytest backend/tests`
     step now sets `TEST_DATABASE_URL` explicitly rather than relying on
     implicit derivation, so the CI config itself states which database the
     suite runs against; the preceding `alembic upgrade head` / `downgrade
     base` / `upgrade head` steps are untouched (they validate migration-
     chain reversibility against the job's own ephemeral `codereader`, a
     different concern from application test isolation, and should not share
     a database with it by coincidence even though both are thrown away when
     the job ends).
     `docs/ops-runbook.md` gains section 7 (the hazard, the fix, how to point
     pytest elsewhere, an explicit "do not bypass the guard" warning) and a
     new alert-catalog row (`DatabaseGuardError` firing is the guard working,
     not an incident); section 1 gains a "back up before any batch" callout
     naming this incident directly.
     RECOVERY: `backend/scripts/backup_db.sh` had been run BEFORE the second
     (24-row) wipe, on unrelated instruction to back up before the D-87
     ingestion work -- pure luck of timing, not a designed safeguard, which
     is itself part of why section 1's "always back up before a batch"
     callout exists now. The dump was restored into a scratch database
     (`backend/scripts/restore_db.sh`, never directly into the live DB),
     the 24 `exercises` rows were confirmed to have zero `(id, version)`
     overlap with the 6 rows already live from the D-87 ingestion, extracted
     as portable `INSERT` statements (`pg_dump --data-only --table=exercises
     --column-inserts`), and applied to the live database. Live count
     verified 6 + 24 = 30 before/after, origins verified as exactly four
     groups (`handauthored_claude`/`spot_the_bug`: 5, `llm`/`predict_the_fix`:
     2, `llm`/`spot_the_bug`: 5, `llm`/`trace`: 18) -- matching the pre-loss
     backup exactly plus the D-87 batch's own contribution. The ~37
     originally-reported exercises remain unrecovered: no backup exists from
     before that first, earlier loss, which is a second argument (independent
     of the wipe mechanism now fixed) for the section 1 backup-before-batch
     discipline going forward.
     Cost: none identified against the fix itself -- every existing test
     still passes unmodified (342/342), and the override is transparent to
     every code path by construction (point d). The recovered content
     inherits whatever quality/review state it already had (`in_review`,
     `human_reviewed=false`) -- this restore did not re-run any gate, it
     reinstated exactly the rows a prior, already-gated orchestrator batch
     had produced.

D-89 Reject-report blind spot on the predict_the_fix derivation path
     (`pipeline/orchestrator.py`'s `_derive_and_publish_ptf`): a rejected
     `derive_artifacts` call only did
     `report.counts[f"{ptf.reject_stage}_rejected"] += 1` and returned --
     `ptf.validation_report`, built in `predict_the_fix.py`'s
     `derive_artifacts` and carrying the full per-check sandbox detail (which
     distractor failed to still-fail, its captured stderr), was discarded.
     The STB candidate path has carried the equivalent receipt to disk since
     D-48 (`_record_reject` -> `publish.write_reject_report`); the PTF path
     never got the same wiring when D-80 added it. Consequence: across
     batches 2-4, all 14 `ptf_sandbox_gate` rejections left zero forensic
     trace -- exactly the "aggregate counter, no per-check telemetry" failure
     D-48 already fixed once, recurring on a path D-48 predates.
     Fix: new `_record_ptf_reject` (mirrors `_record_reject` exactly, per
     D-87's "never build a parallel machinery" rule -- it calls the SAME
     `publish.write_reject_report`) plus `_ptf_candidate_snapshot` (the STB
     triple -- buggy/fixed/test code -- plus the rejected wrong-fix variants'
     code and notes, since a PTF candidate's shape does not fit
     `_record_reject`'s existing `_candidate_snapshot`). `stage` is
     `ptf_sandbox_gate` or `ptf_static_gate`, matching `PTFDerivationOutcome.
     reject_stage` verbatim; a new `concept:{concept}:ptf_rejected` counter
     keeps PTF rejections countable without conflating them with the STB
     spec's own `concept:{concept}:rejected` tally. Per the house rule that a
     reporting path never observed to fire is not a reporting path,
     `test_run_batch_writes_a_reject_report_when_ptf_derivation_is_rejected`
     (`backend/tests/test_m8_predict_the_fix.py`) drives a real rejection (one
     scripted wrong fix IS the verified `fixed_code`, so the sandbox's
     `distractor_1_still_fails_test` check fails it) through `run_batch` end
     to end and asserts the reject JSON lands under `rejects/` with the
     correct stage, spec concept, candidate snapshot, and failing check.
     Cost: none identified -- purely additive telemetry; no gate threshold
     changed.

D-90 Data-loss defect: `spot_the_bug`'s execution-verified `fixed_code` was
     never persisted. `pipeline/publish.py`'s `_stb_grading` stored only
     `grading.artifacts.fixed_code_hash` (a sha256 digest) -- `fixed_code`
     itself existed nowhere in the database, only in-memory during the batch
     that generated it, even though `grading.artifacts.failing_test` (the
     `test_code`) was already the precedent for retaining solution material.
     A digest cannot be inverted, so the 5 `origin="llm"` spot_the_bug
     survivors' fixed_code is gone permanently -- accepted as unrecoverable
     (5 exercises). The 27 `origin="handauthored_claude"` rows only survived
     by coincidence: their fix text still happened to live in
     `pipeline/handauthored_stb_batch{1,2,3,4}.json`, files outside the
     database that nothing guarantees will stay around, and PTF derivation /
     difficulty rebalancing / any future migration was hostage to them. The
     product's trust promise is "the answer was proven by execution"; the
     database was keeping the hash of the proof, not the proof.
     FIX: `_stb_grading` now also writes `grading.artifacts.fixed_code`
     alongside the unchanged `fixed_code_hash` (`pipeline/publish.py`) --
     every spot_the_bug published from here on carries its own verified fix.
     One-time backfill for the 27 already-published handauthored rows:
     `backend/scripts/backfill_stb_fixed_code.py`, joining each DB row to its
     origin batch-file entry on `pipeline.dedup.content_hash(buggy_code)` --
     the SAME AST-normalized hash `orchestrator._evaluate_candidate` already
     computes and stores as `source.content_hash` for every published row
     (LLM and hand-authored both run through that one function), not a fuzzy
     text match. `update_exercise_fields` (unchanged, D-58) permits the
     `grading` update because all 32 spot_the_bug rows are still
     `status='in_review'` -- the live-row immutability guard never engages.
     Backed up first (`backend/scripts/backup_db.sh`, D-88 discipline) before
     any write. RESULT, run against the real dev database: all 27
     handauthored_claude rows matched and backfilled, 0 unmatched, 0 hash
     collisions across the 33 batch-file entries scanned, 0 rows already
     carrying `fixed_code` (script is idempotent past this point). Verified
     independently of the script's own success message: for all 27 rows,
     `sha256(recovered fixed_code) == grading.artifacts.fixed_code_hash`
     already stored in the row -- proof the recovered text is the SAME text
     that was actually executed, not merely a plausible match, matching the
     rigor D-45/D-57/D-88 set for a trust-relevant fix. Cost: none identified
     against the fix; the backfill script becomes dead weight once every row
     has fixed_code, which is the point.

D-91 New entrypoint: `pipeline/ptf_ingest.py` derives a predict_the_fix from
     an ALREADY-PUBLISHED spot_the_bug using HAND-AUTHORED distractors,
     closing the other half of the gap D-80/D-89 left (22 published STB
     survivors with no derived PTF, per the earlier audit). Peer to
     `pipeline/ingest.py` (D-87), same reuse law: static_gate +
     `sandbox_gate.validate_predict_the_fix` run through
     `predict_the_fix.derive_artifacts` completely UNCHANGED -- it already
     takes no LLM client, so a hand-authored batch simply never calls
     `generate_wrong_fixes` (there is no generation step; the distractors are
     already written). `orchestrator._evaluate_candidate` gains no PTF branch
     (its static+sandbox+semantic STB/trace chains do not describe PTF's
     static-gate-on-distractors-only, no-semantic-gates chain -- see the
     earlier audit's section E); the reject path reuses
     `orchestrator._record_ptf_reject`/`BatchReport` verbatim, the exact D-89
     machinery, not a reimplementation.
     Made possible by D-90: `buggy_code` (payload.code), `test_code`
     (grading.artifacts.failing_test), `fixed_code` (grading.artifacts.
     fixed_code, D-90), `context_note` (payload.context_note), and
     explanation summary/principle are all now recoverable from an
     already-published row, so the module reconstructs a minimal duck-typed
     `_STBView` (exactly the attributes `derive_artifacts` reads) from the
     DATABASE, never from a batch file -- the database is the source of
     truth, unlike D-90's one-time backfill which had no choice but to read
     disk. `_STBView` is deliberately NOT a full `STBCandidate`:
     `reason_options`/`correct_reason_id`/`bug_lines`/`self_check`/
     `self_difficulty` are either unpersisted or unread by `derive_artifacts`,
     and fabricating them would manufacture fake provenance for fields
     nothing downstream uses.
     `publish.insert_predict_the_fix` gains an `origin` parameter (default
     "llm", so every existing orchestrator caller is unchanged); the new
     entrypoint passes `origin="handauthored_claude"` -- mislabeling a
     hand-authored derivation as "llm" would corrupt the exact field used to
     trace a quality problem back to its source. Two new `publish.py` helpers
     keep the module boundary law intact (pipeline touches backend only
     through publish.py): `fetch_stb_for_ptf_derivation` (loads the source
     row, refusing anything not `type=spot_the_bug` or no longer
     `in_review`/`live` -- deriving from a pulled/retired row would launder
     whatever made it unfit into new content) and `derived_ptf_exists`
     (skips a spec that already has a derived PTF, so a repeat run over the
     same batch never double-derives).
     VERIFIED (`backend/tests/test_m8_ptf_ingest.py`, both against a real
     published database row, not a mock): (1)
     `test_ptf_ingest_rejects_a_distractor_identical_to_fixed_code_and_writes_
     a_reject_report` -- a hand-authored distractor identical to the verified
     fixed_code (not a distractor at all, a second correct answer) is
     rejected by `ptf_sandbox_gate`, publishes nothing, and writes the D-89
     reject report with the correct stage/concept/candidate snapshot; per the
     house rule that a reporting path never observed to fire is not a
     reporting path. (2)
     `test_ptf_ingest_publishes_a_ptf_from_hand_authored_distractors` -- three
     genuinely wrong, hand-authored distractors derive and publish a PTF
     correctly keyed to the verified fix, with `source.origin=
     "handauthored_claude"`. The sandbox gate itself (`distractor_i_still_
     fails_test`, `distractors_distinct`, determinism) was NOT touched or
     loosened in any way -- both tests exercise the existing, unmodified
     checks from section B of the earlier audit. Cost: none identified; the
     gate's strictness is unchanged, this only adds a second way to reach it.

D-92 M8's private-beta gate becomes a switch, not a wall: new
     `BETA_GATE_ENABLED` setting (`backend/app/config.py`, default `false`)
     going public with open signup, since the roadmap now calls for it and
     the allowlist is a safety control worth keeping in reserve (abuse, cost,
     a bad content incident), not deleting. `beta_allowed`, `beta_invites`,
     and `_apply_beta_invite` are untouched and still populate on every
     login; only the two points that actually ENFORCE the allowlist are
     gated on the new flag: `auth/router.py::github_callback`'s
     `if not user.beta_allowed` (denies the login, no session issued) and
     `auth/service.py::rotate_refresh_token`'s `if not user.beta_allowed`
     (401s an existing refresh cookie). Both had to move together --
     gating only the callback would let a gate-off login mint a cookie in
     `github_callback` and then immediately 401 on the very next
     `/auth/refresh`, reproducing the exact symptom this was built to fix,
     since `rotate_refresh_token` enforces `beta_allowed` independently of
     where the cookie came from. Flipping `BETA_GATE_ENABLED=true` restores
     current (pre-D-92) behavior exactly, with no other code path changed.
     VERIFIED (`backend/tests/test_m8_beta.py`):
     `test_login_succeeds_when_beta_gate_disabled_for_uninvited_user` -- an
     uninvited GitHub user gets a session with the gate off, proven through
     a real `/auth/refresh` call, not just the callback's cookie-set;
     `test_login_still_denied_when_beta_gate_enabled_for_uninvited_user` --
     the same shape of uninvited user is still refused with the gate on.
     The two pre-existing tests that implicitly assumed the gate was always
     on (`test_login_denied_when_not_beta_allowed_no_session_issued`,
     `test_refresh_401s_after_beta_access_is_revoked_mid_session`) now set
     `BETA_GATE_ENABLED=true` explicitly rather than relying on a default
     that just flipped. Frontend: `frontend/src/routes/Login.tsx`'s
     `ERROR_COPY` gains a `beta_required` entry -- found while diagnosing a
     real failed sign-in that every failure mode rendered as an identical
     generic "Sign-in failed. Try again.", making a beta refusal
     indistinguishable from an OAuth/token failure to the user and to
     whoever was debugging it. Cost: one new boolean setting to carry
     through deploys; a deploy that forgets to ever set it back to `true`
     stays permanently open, which is the intended default now, not a
     regression.

D-93 "I don't know" contract: skip is a new terminal `attempts.status` value
     ('skipped'), not a third meaning crammed into `is_correct: bool | None`.
     is_correct already carries two distinct "no verdict" reasons (grading_
     pending, grading_failed) disambiguated by status, not by is_correct
     itself -- adding skipped is the same pattern's natural third case, not
     an overload of it. validate_answer_shape gets a `{"skipped": true}`
     branch per deterministic type (spot_the_bug/trace/predict_the_fix),
     checked as its own exact-key-set branch before the real-answer check,
     never a relaxation of it (docs/05's exact-key-set discipline is
     unchanged for a real answer). summarize is out of scope -- it is
     already dropped from the soft launch (HANDOFF.md) and rubric grading
     has no concept of "no evidence" to short-circuit against.
     grade_deterministic short-circuits on `is_skip_answer()` before ever
     indexing answer["line"]/answer["choice_id"], returning None -- the
     caller (attempts/service.py) uses a separate `is_skip` boolean, not
     `is_correct is None`, to route to status="skipped" vs "graded", so the
     None itself never has to carry which case it is.
     update_concept_state gains a third outcome branch ("skipped", alongside
     "correct"/"incorrect") instead of overloading a bool. A skip:
     increments `declined` (new column, migration 0004), NOT `attempts` --
     it must never inflate the accuracy denominator attempts/correct drive;
     schedules CONCEPT_INTERVAL_SKIPPED_DAYS=1 (sooner than WRONG's 2 days),
     because an honest "I don't know" is a CLEANER signal than a wrong guess
     (no misconception was planted, just an absence of evidence) and is
     worth re-testing sooner; decays mastery by a gentler multiplier (0.85
     vs WRONG's 0.7), with no directional target term at all -- a skip
     doesn't assert the user believes something incorrect, so it shouldn't
     be pulled toward 0 the way a wrong guess's target=0 term does, only
     reflect a mild forgetting-curve lapse. Cost: one migration, one new
     status value threaded through AttemptResponse.status/SessionProgress
     and both update_concept_state call sites (attempts/service.py,
     jobs/grading_retry.py).
     VERIFIED (backend/tests/test_m9_skip_contract.py): a skipped
     spot_the_bug/trace/predict_the_fix attempt is accepted, returns
     status="skipped" with a full reveal and is_correct=None; a skip
     schedules next_review_at one day out vs. two for an equivalent wrong
     answer on a fresh concept; user_concept_state.attempts and
     accuracy_by_type's denominator are unchanged by a skip (only declined
     moves); the old exact-shape rejection for a real (non-skip) malformed
     answer is untouched (a negative test: {} and {"skipped": false} still
     422).

D-94 GET /v1/me/activity: the contribution-grid data source is
     daily_sessions, not a new table -- it is already one row per
     user-active-day, PK'd on (user_id, session_date), and `completed_at`
     already distinguishes finished vs. opened-but-not-finished (the same
     table admin/service.py::compute_retention already reads as the
     canonical "was the user active" signal). Default window: 365 days
     ending "today" in the user's own local timezone (local_date_for), the
     same date semantics sessions/streaks already use -- not naive UTC
     `date.today()`, which would show the wrong grid boundary near midnight
     for a user outside UTC. Cost: none identified; no new table, no new
     precomputed aggregate to keep in sync.

D-95 POST /attempts response gains `session.first_completed_session: bool`.
     Computed inline at the exact moment `daily_session_row.completed_at`
     flips from NULL (the same code path that already does the flip), by
     counting `daily_sessions` rows with `completed_at IS NOT NULL` for the
     user INSIDE the same transaction -- the just-flipped row is already
     visible to that count, so 1 unambiguously means "this is the user's
     first-ever completed day." No new column: `users`/`user_stats` gained
     no `first_session_at`/`sessions_completed` field, since the count is
     cheap (one indexed-PK aggregate) and only ever runs on the one request
     per user per day that actually completes a session, not on every
     attempt. Cost: one extra COUNT query, only on session-completing
     requests.

D-96 reviews: new table, shaped like disputes (text+CHECK not a Postgres
     enum, timestamptz everywhere) but upserted instead of append-only --
     one review per user, enforced by a DB-level UNIQUE on user_id, not
     just upsert-shaped application logic, so a concurrent double-submit
     for the same user still can't produce two rows. GET /admin/reviews
     reuses the existing `_require_admin_token` shared-secret gate verbatim
     (the same placeholder HANDOFF.md already flags as "fine for a 20-30
     person beta, acknowledged weakness") rather than inventing new admin
     auth -- consistent with the instruction to inherit it, not fix it
     here. Cost: one migration, one new module (app/reviews/), inherits
     the admin auth weakness rather than deferring/fixing it (already
     tracked).

D-97 GET /session/today/review reuses build_reveal()/build_summarize_reveal()
     (attempts/grading.py, attempts/rubric.py) verbatim -- the exact
     functions POST /attempts and GET /attempts/{id} already call -- rather
     than re-deriving a "review" shape from exercise.grading/explanation a
     second time. Only exercises the user actually attempted today appear;
     an unattempted exercise has no answer/verdict/reveal to show yet.
     Lives in sessions/service.py (not a new domain module) since it is a
     read over the same today's-session data get_today_session already
     builds -- module law respected by importing attempts/grading.py and
     attempts/rubric.py's pure builder functions (no import of
     attempts/service.py, no cycle: attempts/service.py already imports
     sessions/service.py the other direction). Cost: none identified; no
     grading/explanation JSONB is ever dumped wholesale, same allowlist
     discipline as every other reveal-returning endpoint.

D-98 UX upgrade, deliberate override of docs/08b: DARK-ONLY, not
     dark-offered-default-light. docs/08b is explicit that "dark-by-default
     is the single most common slop tell" and specifies an explicit toggle
     defaulting to light. The product owner overrode this for the M9 UX
     upgrade: a developer-tool reading surface is judged against a
     different reference class than the landing-page corpus that
     calibration was defending against, and a considered, singular dark
     surface is a legitimate identity choice for this audience, not a
     default nobody chose. The toggle, the light token set, and theme.ts's
     switching logic are deleted entirely, not merely defaulted -- keeping
     a dead toggle around would invite exactly the "how do I get light
     mode" support burden a real single-surface product doesn't have.
     WCAG AA contrast on the one dark surface remains a hard requirement
     (docs/08's quality floor is unchanged by this override). Cost:
     docs/08b's "never the default" line is now wrong for this app; this
     entry is the record of the divergence, not a rewrite of docs/08b
     itself.

D-99 UX upgrade, deliberate override of docs/08b: a contribution grid
     (GitHub-style, D-94's GET /v1/me/activity), not "streak history = a
     column of gutter ticks." Same signature world (a developer's own
     contribution graph, not a borrowed dashboard widget), richer
     information density for the same idea -- gutter ticks show only a
     capped recent run, the grid shows the full year. The non-negotiable
     color law is unchanged and re-affirmed here explicitly because this is
     the highest-risk place to violate it by habit: green/red stay reserved
     for correctness only, so the grid is built from --color-action (the
     annotation-ink blue) at varying intensities, never green -- a green
     grid would both break the semantic law and make the app a literal
     GitHub-contributions clone, the opposite of docs/08's "not from
     startup-landing vernacular" brief. Cost: none identified against the
     color law (blue-intensity scale costs nothing docs/08b didn't already
     have -- --color-action exists); docs/08b's literal gutter-ticks-only
     line is superseded for streak history specifically, gutter ticks may
     still appear elsewhere (e.g. session progress) where docs/08b already
     specifies them.

D-100 review_history: new append-only table alongside D-96's reviews, not a
     replacement. reviews.user_id stays UNIQUE and upserted (the "current
     opinion" a dashboard would show); review_history gains a row on every
     POST /v1/me/review with no UNIQUE constraint and no UPDATE path, ever
     -- the record of how the current opinion got there. Reason: a rating
     that moves from 3 to 5 over a beta is signal the upsert-only shape
     was silently destroying. GET /admin/reviews now nests each user's
     full history (oldest-first) under their current review rather than a
     second endpoint, since every caller of the review list wants both
     together. Cost: one migration, one model, one extra INSERT per
     review submission (same transaction, so no new failure mode); the
     reviews table's shape and POST /v1/me/review's response contract are
     unchanged.

D-101 Content-integrity defect (red-team C1): every published `trace` exercise
     keyed its correct answer to choice id "a". The generator prompt
     (`prompts/generator_trace_python_v1.md`) pins the correct choice to "a",
     and `publish._trace_payload` copied the generator's choices verbatim with
     NO shuffle -- unlike `predict_the_fix.derive_artifacts`, which has always
     `rng.shuffle`d its choices. Confirmed against the live DB: all 39 trace
     rows (8 live + 31 in_review) had `correct_choice_id='a'` with "a" first in
     `payload.choices`. A client submitting `{"choice_id":"a"}` scored 100% on
     the entire trace corpus without reading the code -- and poisoned every
     trace exercise's solve-rate/percentile, trace-concept mastery, and
     spaced-repetition, since "correct" no longer meant the user could trace.
     This is NOT an invariant-2 serializer leak: the session allowlist
     (`sessions/service.py` `_serialize_payload`, `schemas/session.py`, both
     `extra="forbid"`, dropping `misconception`) holds; the bias was upstream
     in content generation. The prompt is left alone (D-46/D-53 lesson: a prompt
     fighting a downstream mechanic is the wrong layer) -- the shuffle belongs
     at publish, exactly where PTF already does it.
     FIX 1a (code, new rows): `publish.insert_candidate` now shuffles trace
     choices at publish time via `reassign_shuffled_choice_ids` -- a new
     module-level helper extracted so the publish path AND the one-time
     migration (below) share ONE shuffling approach, never a second. It mirrors
     PTF's shuffle-then-zip-onto-ids pattern (over the candidate's own id set,
     sorted, so a/b/c/d stay a/b/c/d) and is fed the SAME batch `rng` the
     orchestrator already threads to PTF derivation. `payload.choices` (id +
     order), `grading.correct_choice_id`, and `explanation.why_wrong`'s
     choice_id references all move together off the single shuffle
     (`_remap_trace_why_wrong`), so the answer key can never drift apart from
     the shown options. No gate touched; the correct choice's text stays the
     sandbox-captured stdout (the belt-and-braces substitution moved into the
     shuffle helper unchanged). Negative test
     (`test_m3_publish.py::test_published_trace_correct_choice_is_distributed_
     not_always_a`): 40 published traces off one shared rng must spread
     correct_choice_id across >=3 ids and never be constant -- it fails on the
     pre-fix code (all "a") and passes now; per-row it also asserts the key is
     in the shown choices, the correct text is preserved, and why_wrong never
     names the correct id. The existing fixture assertion that pinned the
     correct choice to index [0] was rewritten to key by correct_choice_id
     wherever the shuffle placed it.
     FIX 1b (data, existing rows): `backend/scripts/reshuffle_trace_choices.py`
     re-shuffles already-published trace rows IN PLACE, reusing
     `reassign_shuffled_choice_ids`/`_remap_trace_why_wrong` verbatim (same
     shuffle as 1a). Seeded per-row from the immutable exercise id
     (reproducible). The load-bearing safety is a text-invariant assertion PER
     ROW: the choice whose id == correct_choice_id AFTER must carry the SAME
     TEXT the correct choice had BEFORE, the full set of choice texts must be
     unchanged, and every text->misconception mapping preserved -- a violation
     aborts rather than writing a mis-keyed exercise. Writes go through the
     D-58 `update_exercise_fields` immutability guard, NOT around it. Run
     against the real dev DB (backed up first, D-88 discipline): dry-run proved
     0 text-invariant errors across all 39 and a spread of {a:14,b:9,c:7,d:9};
     `--apply --status in_review` re-shuffled the 31 in_review rows
     ({a:11,b:9,c:5,d:6}); a migrated row verified coherent end to end
     (correct_id=d, choice_ids=a-d, why_wrong=a,b,c, correct text == captured
     stdout). Existing `attempts` rows were never touched.
     THE 8 LIVE ROWS ARE DELIBERATELY NOT YET FIXED. `update_exercise_fields`
     correctly REFUSES an in-place content update to a live row (invariant 3:
     exercises immutable per (id,version), fixes bump version). Re-keying them
     in place would also require bypassing that guard AND would desync the 22
     existing attempts on them (a stored `answer.choice_id` chosen under the old
     layout would point at different option text after a relabel; is_correct is
     frozen but the review display would mislabel). Per the engagement's
     inviolable rule ("if a fix appears to require loosening an invariant, STOP
     and report"), the live rows are held for a deliberate decision (pull vs.
     version-bump-and-re-review vs. an explicit logged override) rather than a
     silent guard bypass.
     LIVE-ROW RESOLUTION (chosen: version-bump + re-review; the immutability
     guard is NOT overridden): `reshuffle_trace_choices.py --bump-live` calls
     `publish.fix_and_bump` on each of the 8 live rows, creating a shuffled
     in_review v2 (same shared shuffle) while leaving v1 live and untouched --
     v1 keeps its 22 attempts honest against the exact version those users
     answered. The re-key is proven twice: `_reshuffled` asserts v2's correct
     text == v1's correct text before the write, and the script re-reads v2
     after the write and re-asserts the text survived the round trip. Verified
     against the real DB (backed up first): 8 v2 rows created; e.g. 16065f30
     v1 correct='a'/text='2' -> v2 correct='d'/text='2' (id moved, text
     preserved, why_wrong remapped to a,b,c). Distribution across the 39
     fixed-and-shippable in_review rows (31 originals + 8 v2): {a:14,b:9,c:7,d:9}
     -- within normal variance of a provably-uniform 4-way shuffle at n=39, not
     constant. The operator approves each v2 (`review_cli approve`) and only
     then is the matching v1 pulled (`review_cli pull` / `publish.pull`), so
     `exercises_current` (DISTINCT ON (id) WHERE status='live' ORDER BY version
     DESC) serves v2 the moment it goes live and never serves a pulled v1 nor
     an unapproved in_review v2. The 8 v1 rows remain live+gameable until that
     deliberate approve->pull, which is the one manual step this fix leaves open
     by design (status changes stay deliberate, HANDOFF/CLAUDE.md).

D-102 History-loss defect in the pull path, found during the C1/D-101 work
     (pulling the 8 re-keyed trace v1s destroyed a user's COMPLETED session).
     `sessions/service.purge_sessions_referencing` (D-58) deleted EVERY
     daily_sessions row referencing a pulled exercise from yesterday onward,
     including rows with `completed_at IS NOT NULL`. Pulling one bad exercise
     therefore erased a finished day from every user who had already COMPLETED
     a session containing it: `total_sessions` dropped, the activity heatmap
     square reverted from completed to opened, and the streak evidence for that
     day vanished -- silently rewriting the retention mechanic. Correct-as-
     written (D-58 said "still-servable") but wrong-as-designed: a completed
     session is never served for ANSWERING again, so swapping content out of it
     protects the user from nothing; the only effect is deleting history they
     earned. Confirmed by real reproduction: the D-101 pull purged 21 cached
     sessions, at least one a completed same-day session, which surfaced this.
     FIX: `purge_sessions_referencing` gains a `completed_at IS NULL` predicate
     alongside the existing `session_date >= yesterday`, so ONLY in-flight
     sessions are purged. D-58's real purpose is untouched -- an unfinished
     session must still never serve pulled content, and it doesn't: the
     in-progress purge (delete row + Redis key, forcing a fresh resample) is
     unchanged. A kept completed session still renders because pull flips
     status to 'pulled' but never DELETES the exercise row, so the already-
     answered exercise still resolves on the review screen.
     NEGATIVE TEST (`test_m7_pull_exercise.py::test_pull_keeps_completed_
     sessions_but_purges_in_progress_ones`): two users reference the same
     exercise, one via a completed daily_session and one via an in-progress
     one; a pull leaves the completed row + cache intact and purges only the
     in-progress row + cache (`purged == 1`). Fails on the pre-fix code (purged
     both). The two existing pull tests still pass -- the built, not-yet-
     completed session they exercise is in-flight, so it is still purged.
     RECOVERY: the completed daily_sessions rows the D-101 pull destroyed are
     restored from the pre-pull backup (`codereader_2026-07-12T2125Z.dump`,
     taken minutes before the approve/pull batch), re-inserting only the
     completed rows now missing from the live DB; the exercise rows they
     reference still exist (pulled, not deleted), so the restored rows resolve.
     Exact rows restored are in the report accompanying this entry.

D-103 Frontend robustness (red-team C2): a malformed/partial grade `reveal`
     threw during render and, with NO React error boundary anywhere in the
     tree, white-screened the entire SPA mid-session (reload re-hit the same
     data -> persistent blank page). `AttemptResponse.reveal` is typed
     `Reveal | null`, so `null` is a contract-legal value on a graded/skipped
     attempt, and the per-type reveal views dereferenced `reveal.correct_lines`
     / `reveal.explanation.*` unguarded. Two-layer fix, no behavior change to
     the happy path:
     (a) `components/ErrorBoundary.tsx` -- a class boundary (getDerivedState
     FromError + componentDidCatch -> Sentry.captureException, a no-op without a
     DSN, so turning a white-screen into a fallback never hides the bug).
     Placed at the app root (`main.tsx`, `FullPageErrorFallback` with a reload)
     AND around the per-exercise session content (`Session.tsx`, keyed by
     `currentIndex` so it remounts fresh each exercise), whose fallback is a
     "Skip this exercise" button wired to `handleNext` -- losing one broken
     exercise beats losing the whole session.
     (b) Defense-in-depth guards in `revealViews.tsx` / `Reveal.tsx`: each
     per-type view early-returns a readable "explanation isn't available" note
     when its required reveal fields are missing, so a partial reveal degrades
     to a note rather than relying on the boundary at all.
     VERIFIED by a real Playwright test (`e2e/reveal-error-boundary.spec.ts`):
     it intercepts POST /v1/attempts to return a graded response with a
     non-object `reveal` (1), which throws `'explanation' in 1` in Reveal's
     render; the test asserts the boundary's "Skip this exercise" state renders
     (the browser console confirms the throw was caught, not a white screen)
     and that skipping advances the session (next exercise or completion). Ran
     green against the real dev stack. NOTE for future e2e runs: seed_e2e.py's
     refresh token ROTATES on first use, so every Playwright run needs a FRESH
     seeded token -- reusing one lands on /login and looks like a test failure.
     Two pre-existing, out-of-scope items surfaced and are NOT fixed here (only
     noted): the M6 `session.spec.ts` is stale against the M9 dashboard-at-"/"
     (D-98/D-99) so it fails its first `toHaveURL(/session)` assertion; and the
     dashboard's all-or-nothing `Promise.all` (red-team M6) intermittently
     blanks the landing page on a transient fetch failure.

D-104 Concurrency defect (red-team H1): the POST /attempts advisory lock was
     keyed per-EXERCISE, but the data it protects is per-USER. `submit_attempt`
     took `pg_advisory_xact_lock(hashtext(user_id), hashtext(exercise_id ||
     ':' || date))` (D-66), which serializes only two submits of the SAME
     exercise. But `_update_streak_and_attempt_count` mutates per-user
     `user_stats` and writes at most one `streak_events` row per user per local
     day. Two concurrent first-of-day submits of DIFFERENT exercises (two tabs,
     a retry storm) took different lock keys, so they never serialized: both
     read `last_active_local_date != today`, both took the "extended" branch,
     and wrote TWO `streak_events` rows (invariant 5: one transition must write
     exactly one row) plus a lost-update on `total_attempts` (both read N, both
     wrote N+1). Streak is the retention mechanic; this silently corrupted its
     audit trail and undercounted attempts.
     FIX (two layers, per the "prefer a DB constraint, it cannot be raced"
     steer):
     (1) The advisory lock is re-keyed to `(user_id, session_date)` -- lock_b
     is the date only, not exercise||date. This serializes EVERY same-day
     submit by a user, so the second observes the first's committed stats
     (last_active == today -> no second transition) and, for the same-exercise
     case, its committed attempt (correct 409). The same-exercise protection
     D-66 added is preserved (same-exercise submits still share the lock),
     just widened to also cover the cross-exercise per-user race.
     (2) Migration 0007 (`db/schema.sql` updated to match) adds a PARTIAL
     UNIQUE INDEX `uq_streak_events_one_transition_per_day` ON streak_events
     (user_id, local_date) WHERE event IN ('extended','reset') -- the
     un-raceable DB backstop: the database itself refuses a second transition
     row for a (user, day), independent of any application race. Scoped to
     extended/reset on purpose: 'repaired' (D-68 tz reconciliation),
     'freeze_used', 'adjusted' are separate event kinds that can legitimately
     co-occur with a transition on the same day and stay unconstrained. No
     existing live rows violated it (checked: zero duplicate transition rows
     before adding the index). Neither the streak transition logic nor invariant
     5 is weakened -- the fix ENFORCES invariant 5, it does not relax it.
     TESTS (real concurrency, not sequential awaits):
     `test_concurrent_first_of_day_submits_of_different_exercises_write_one_
     streak_event` fires two `asyncio.gather`ed submits of two DIFFERENT
     exercises as the user's first activity of the day and asserts exactly ONE
     streak_events row, `total_attempts == 2`, `current_streak == 1` (fails on
     the pre-fix per-exercise lock: two rows + total_attempts 1);
     `test_streak_events_unique_index_rejects_a_second_daily_transition` proves
     the DB backstop directly (a second extended/reset row for the same (user,
     day) raises IntegrityError; a 'repaired' row on the same day does not).
     ONE existing test was corrected, NOT weakened: `test_m4_streaks.py::test_
     streak_audit_invariant_every_transition_writes_a_streak_event_row`
     simulated "the next day" by rewinding `last_active_local_date` while
     leaving the real `today` fixed, so BOTH of its transition rows got
     `local_date = today` -- an impossible production state (a transition row's
     local_date is always the real transition day, and there is at most one per
     day). The test now also rewinds the first row's `local_date` to yesterday,
     faithfully modeling two transitions on two different local days; its
     invariant-5 assertions (two rows, both 'extended', (0,1) then (1,2)) are
     unchanged. Cost: the lock now serializes a user's genuinely-concurrent
     same-day submits of different exercises (for summarize, the loser waits up
     to GRADER_TIMEOUT_S) -- scoped to one user's own same-day traffic, never
     unrelated users.

D-105 Frontend flow defect (red-team H2): onboarding was enforced only on the
     "/" landing (RootGate), not as a real gate. `App.tsx`'s `RequireAuth`
     checked only auth `status`, never `user.onboarded`, so a hard refresh or
     deep-link straight to `/session` (or `/profile`, `/review`) reached the
     protected screen with no level set -- and the session sampler's difficulty
     bands (LEVEL_BANDS) are undefined without a level. FIX: `RequireAuth` gains
     a `requireOnboarded` prop (default true) and redirects an authenticated-
     but-not-onboarded user to `/onboarding` from ANY protected route. The
     `/onboarding` route moves to a dedicated `OnboardingRoute` that requires
     auth but NOT onboarding (requiring it there would loop) and, closing the
     other half of the same audit finding, redirects an ALREADY-onboarded user
     to "/" so they can't silently re-pick their level. No backend change.
     VERIFIED (`frontend/e2e/onboarding-gate.spec.ts`, hermetic -- stubs POST
     /v1/auth/refresh to set `onboarded` directly, so no seeded user and no
     refresh-token rotation are involved): a non-onboarded user deep-linking to
     /session lands on /onboarding (the level-pick heading renders); an
     already-onboarded user visiting /onboarding lands back on the dashboard.
     `tsc --noEmit` clean. Cost: none; the redirect is a pure client-side gate,
     and PATCH /me already persists the level as the onboarding action (D-42).

D-106 Frontend resilience (red-team FIX-A, promoted to launch blocker): the
     Dashboard (`Promise.all` of 3 fetches) and Profile (`Promise.all` of 6)
     blanked the ENTIRE page if ANY single fetch rejected -- a transient 5xx on
     one secondary panel took down the first screen every user sees daily, the
     real cause of the "Could not reach the server" full-page failures observed
     during the C2 work. FIX: a shared `frontend/src/lib/usePanel.ts` hook
     (`Panel<T>` = loading | ok | error) loads each panel INDEPENDENTLY, so a
     failed fetch degrades only its own panel. Dashboard: the primary "enter
     session" CTA now renders in every state except a confirmed empty pool --
     even a failed session fetch shows the CTA (linking to /session) plus a
     "you can still start" note, and the two secondary panels (upcoming
     reviews, recent sessions) show their own "couldn't load" notes. Profile:
     the same via a `withPanel` wrapper -- streak, activity, accuracy-by-type,
     accuracy-history, concepts, and recent-sessions each load and degrade
     independently, and the already-best-effort review-status fetch stays
     out-of-band (its failure only hides the "review again" affordance). No
     more all-or-nothing top-level `error` state or `if (!a || !b || ...)
     Loading` gate on either screen. VERIFIED (`frontend/e2e/dashboard-
     resilience.spec.ts`, hermetic): with /v1/me/concepts stubbed to 500 and
     the session fetch succeeding, the page still renders (the greeting header
     is visible), the primary CTA is present AND navigates to /session on
     click, and only the failed panel shows a "couldn't load upcoming reviews"
     note -- never a blank page. `tsc --noEmit` clean; Profile inherits the
     same pattern through the shared hook. Cost: none identified; three/six
     independent fetches instead of one batched await, same total requests.

D-107 Request-layer hardening (red-team, the three mediums), all in
     `app/main.py`:
     (M1) An UNAUTHENTICATED flood of POST /v1/attempts hit no rate limiter at
     all: the endpoint was exempted from the default middleware (D-64) because
     it self-enforces a stricter 10/min PER-USER limit -- but that limit lives
     inside submit_attempt, AFTER `require_access_token`, so a request with a
     missing/garbage token was 401'd before any limiter ran (verified live:
     15x401, 0x429). FIX: `_needs_default_rate_limit` no longer exempts POST
     /v1/attempts; the `default_rate_limit` middleware instead skips it ONLY
     when the request is authenticated (identity is `user:...`), so an
     authenticated user still defers to the per-user limit and is not
     double-limited, while an unauthenticated one (identity `ip:...`) is capped
     by the default IP limit before it ever reaches auth. Test:
     `test_unauthenticated_attempts_flood_is_rate_limited_by_ip` (limit 2 ->
     [401, 401, 429]) plus `test_authenticated_attempts_are_not_double_limited_
     by_the_default` (default limit 1 -> two authenticated attempts both 200).
     (M2) An unhandled exception fell through to Starlette's default plain-text
     "Internal Server Error": no uniform JSON body, no request_id for a user to
     quote to support, and -- that path being outside the header middlewares --
     no security headers (verified live). FIX: an `@app.exception_handler(
     Exception)` returns `error_body("internal", ...)` with the request_id and
     re-applies the security headers (and HSTS in prod) itself, since its
     response does not pass back through the header middleware. The exception is
     never leaked: a fixed generic message to the client, the traceback to the
     server log (exc_info) and Sentry only. FastAPI resolves ApiError /
     RequestValidationError to their existing, more-specific handlers, so only
     genuinely-unhandled errors reach this one. Test:
     `test_unhandled_500_returns_uniform_json_shape_headers_and_no_stacktrace`
     (drives the debug endpoint's RuntimeError; asserts JSON code 'internal',
     a request_id, X-Content-Type-Options/X-Frame-Options/X-Request-ID present,
     and that 'Traceback'/'RuntimeError'/the exception message are absent from
     the body). Verified live too.
     (M3) A client-supplied X-Request-ID was trusted verbatim -- written into
     every structured log line and a Sentry tag and echoed in the response --
     a log-injection / correlation-spoofing vector. FIX: `_resolve_request_id`
     honors the incoming header only if it matches `^[A-Za-z0-9_-]{1,64}$`
     (blocking spaces, newlines, `=`, `:` and over-long values), otherwise
     generates a server id; a trusted upstream can still propagate a
     well-formed trace id. Test: `test_client_supplied_request_id_is_sanitized`
     (an injection-shaped value is replaced with a `req_...` id; a well-formed
     one is echoed). Verified live. Cost: none identified; all three are
     request/middleware-layer changes with no route logic touched, and no gate,
     guard, or invariant is weakened -- these only ADD enforcement/robustness.

D-108 Smoke-suite repair (red-team FIX-B): the M6 Playwright smoke
     (`frontend/e2e/session.spec.ts`) asserted `toHaveURL(/session)` at "/",
     but "/" became the dashboard at M9 (D-98/D-99), so the WHOLE smoke suite
     failed on its first assertion -- red for a benign routing reason, giving
     zero signal for the entire M9 era. FIX (navigation, no coverage dropped):
     the test now clicks the dashboard's "Enter sandbox" CTA to reach /session,
     then proceeds through the session exactly as before. Running it green
     again surfaced two follow-ons:
     (a) The final `expect(seenTypes.has('predict the fix'))` assertion was
     ~1-in-5 flaky: the session's type mix is SAMPLED from the live pool (~8
     predict_the_fix among ~25 live exercises), so a 5-slot session misses it
     often. Requiring a specific sampled type is not a meaningful smoke
     invariant. Relaxed to the real one -- a full session of whatever it served
     plays through reveal to completion -- and the deterministic per-type UI
     coverage it was aspirationally providing is MOVED (not deleted) to a new
     hermetic `frontend/e2e/predict-the-fix.spec.ts` that stubs a PTF session +
     graded reveal and always exercises the PTF answer radios and reveal.
     Net: coverage up and no longer flaky.
     (b) `Session.tsx` still loaded via `Promise.all([getSessionToday(),
     getMeStats()])` -- the same all-or-nothing pattern FIX-A (D-106) fixed on
     the dashboard, but here on the CORE session player: a transient failure of
     getMeStats (only the gate's streak count) blanked the entire session with
     "Could not reach the server." Made getMeStats best-effort (the session
     loads on getSessionToday alone; the gate shows a 0 streak if stats fail),
     extending FIX-A's resilience to the one screen that matters most.
     VERIFIED: session.spec.ts runs the full seeded session (dashboard ->
     /session -> answer each served type -> reveal -> "Session complete") green;
     predict-the-fix.spec.ts, onboarding-gate.spec.ts, dashboard-resilience.
     spec.ts pass; reveal-error-boundary.spec.ts passes (the Session change
     removed its getMeStats-flake failures). `tsc --noEmit` clean. NOTE on the
     e2e harness (also in D-103): seed_e2e.py's refresh token rotates on first
     use, so each token-consuming spec needs its OWN fresh seed -- the two
     real-backend specs (session, reveal) are run one fresh-token at a time;
     the three hermetic specs need no token. The intermittent browser->API
     "Could not reach the server" is an environment artifact (Windows/docker/
     vite dev networking; curl to the API always succeeds), now with a far
     smaller blast radius after (b).

D-109 Review-gate defect: validation_report_url stored an ABSOLUTE path rooted
     at the WRITER's view of the repo, so the human review packet showed "no
     validation report on disk" for 92 of 98 exercises while every report sat
     on disk in pipeline/validation_reports/.
     ROOT CAUSE: `publish.write_validation_report` returned `str(path)`, where
     path = `settings.validation_reports_dir / f"{id}_v{n}.json"` and
     `validation_reports_dir` absolutizes against
     `REPO_ROOT = Path(__file__).resolve().parent.parent` -- i.e. the repo root
     AS THE WRITING PROCESS SEES IT. The pipeline runs containerised with the
     repo bind-mounted at /work, so it persisted
     `/work/pipeline/validation_reports/<uuid>_v1.json`, while
     `review_cli.load_validation_report` did a literal `Path(url).exists()` on
     the HOST, where /work does not exist. Confirmed in the DB: the 99
     container-written rows all carry a /work path; the 6 that resolved carry
     `D:\projects\codereader\...` and were published from a host-side run. Not
     missing data -- a pointer that was only ever valid on the machine that
     wrote it.
     WHY IT HID: the reader degrades gracefully (returns None on a missing
     file, by design, so review never crashes on a moved report), and the
     packet renders that None as the same "no validation report on disk" text
     it would use for a genuinely absent report. A container/host path mismatch
     was therefore indistinguishable from "the pipeline never wrote receipts".
     A write-then-read-back test on ONE machine passes even with this bug,
     which is exactly why it shipped.
     FIX: store a REPO-RELATIVE POSIX path (`pipeline/validation_reports/
     <uuid>_v<n>.json`), which resolves identically inside and outside the
     container. `pipeline/config.py` gains the pair `repo_relative_str` (writer)
     and `resolve_repo_path` (reader); publish.py stores the former, review_cli
     resolves via the latter. `resolve_repo_path` asks is_absolute() of BOTH
     PurePosixPath and PureWindowsPath, because a POSIX-absolute string like
     /work/x is NOT absolute to pathlib on Windows (it is drive-relative), and
     joining it onto the repo root would silently manufacture D:/work/x and
     make a missing report look present. Legacy absolute pointers are honoured
     as-is rather than rewritten at read time; the backfill owns that.
     BACKFILL: migration 0008_validation_report_relpath rewrites the absolute
     rows to the relative form. Idempotent (rows already canonical are excluded)
     and scoped to the `pipeline/validation_reports` segment so a reports dir
     deliberately configured outside the repo is left alone. It touches ONLY
     validation_report_url; no exercise status is changed. downgrade() is a
     deliberate no-op: the original values encoded the writer machine's root,
     which is not recoverable from the stored string, and restoring it would
     just restore the bug.
     TESTS (the property that actually broke, not a same-machine round trip):
     the stored pointer is rooted under NEITHER PurePosixPath nor
     PureWindowsPath; a freshly published exercise's pointer resolves to a
     readable file whose JSON equals the report that was written (a path that
     has never been read back is not a path); and a NEGATIVE test that a legacy
     /work pointer is never grafted onto the repo root.
     VERIFIED: 105 of 105 exercises with a pointer now resolve to a readable
     report (0 unresolved, was 6 of 105). The regenerated packet's 77 in_review
     exercises ALL carry a real quality line; zero "no validation report on
     disk". The remaining 5 rows have a NULL pointer and are hand-authored
     seeds (origin=seed_handauthored) that never ran the pipeline, so they have
     no receipts to point at -- correct, not a path failure. None are in_review.
     ALSO FIXED (same file, cosmetic but actively misleading): the `packet`
     command counted sections with `packet.count('### ')`, which also matches
     every '#### Code' sub-heading, reporting "616 exercise(s)" for a
     77-exercise packet. Now counts section headings only.

D-110 First full human review gate run (M8 part 2): 77 candidates reviewed, 4
     killed, 73 approved to live. Live pool goes 25 -> 98, in_review 77 -> 0.
     This is the first review pass made possible by D-109; before that fix, 92
     of 98 exercises showed "no validation report on disk" and the receipts a
     reviewer needs were unreadable.
     KILLED (4, all spot_the_bug, all v1, in_review -> retired; no live row was
     touched). Every one is the same failure mode: the distractors are
     PARTIALLY DEFENSIBLE, so more than one option can be argued correct and
     the exercise stops having a single defensible answer.
     - dbd2f905-058d-473d-8a0f-7725d6393a13: has_bug=false with an EMPTY answer
       key, but the STB UI requires a line tap. Literally unanswerable -- the
       one shape the type cannot express. Worth noting as a generator/UI
       contract gap, not just a bad candidate: nothing upstream forbids
       has_bug=false for a type whose UI demands a line selection.
     - 6d8ce525-1874-4f80-be07-23e7b73353ca (d10) and
       1b77eca4-eeb3-4a6f-8948-1403bfdc4799: three hedged "could / may /
       risking" distractors. A hedged distractor is not wrong, it is merely
       weaker, so the answer key is a judgement call rather than a fact.
     - 1803aa12-10cd-47c2-8e6d-1efbf2f7362d: defect_audit=flag AND hedged
       distractors -- the gate flagged it and the review agreed.
     APPROVED (73: 21 spot_the_bug, 21 predict_the_fix, 31 trace). The id list
     was verified against the in_review set before the batch ran (exact match,
     no strays, no omissions); all 73 succeeded, zero failures. Backup taken
     first via backend/scripts/backup_db.sh (D-64).
     Final content state: 98 live (39 trace, 29 spot_the_bug, 29
     predict_the_fix, 1 summarize), 8 pulled, 4 retired, 0 in_review.
     KNOWN GAP, and the #1 post-launch CONTENT target (a roadmap item, NOT a
     defect -- nothing is broken and nothing is being disabled for it):
     the senior end of the live pool is carried almost entirely by trace.
     - spot_the_bug and predict_the_fix pile up at d3-d4 (23 of 29 each, ~79%)
       and spot_the_bug has a HARD d6 CEILING: zero STB above difficulty 6.
     - The senior band is (5, 10) with target 7 (D-61). It holds 33 live
       candidates -- but 23 of those 33 (70%) are trace, and every in-band STB
       sits at the band FLOOR (d5-d6). The boss slot (needs d>=9) has 7
       candidates: 6 trace, 1 predict_the_fix, 0 spot_the_bug.
     - Consequence: a senior gets a FULL, working session (the sampler does not
       starve -- D-61 degrades gracefully and never raises, and this was
       verified, not assumed), but it is trace-heavy and its bug-finding
       content is mid-difficulty. A senior never sees a senior-difficulty
       spot_the_bug, because none exists.
     - Note the 4 kills removed from the thinnest band (one was d10), so the
       gap is now structural rather than incidental.
     DECISION: senior stays ENABLED. Disabling it was considered and rejected.
     The case for disabling rested on "the level cannot be filled", which the
     numbers above disprove: 33 in-band candidates, a full session, no sampler
     bug, and zero users at level='senior' today (36 users: 35 mid, 1 junior),
     so there was no affected population to protect. A working-but-imperfect
     tier is not hidden: the soft launch EXISTS to tell us whether seniors show
     up and whether the trace-heavy mix reads as too easy, and hiding the tier
     throws away exactly that signal. We launch with senior enabled and
     imperfect and let real senior usage decide what to author first.
     ACTION: author d7-d10 spot_the_bug and predict_the_fix. That, not a
     feature flag, is what closes this.

D-111 The session gate is removed: reaching /session now opens the player
     directly. Reported from real use -- clicking "Enter sandbox" on the
     dashboard appeared to load an "old, broken, left-aligned" screen. It was
     not old UI and nothing was stale: it was `SessionGate`, current code,
     doing exactly what it was written to do.
     WHAT WENT WRONG: the product brief says a user must never be dropped into
     a session automatically. That was implemented as a second confirmation
     SCREEN -- Session.tsx opened in a 'gate' phase whose primary action was a
     button ALSO labelled "Enter sandbox" (the same words as the dashboard CTA
     that had just been clicked). So the deliberate-entry requirement was
     satisfied twice, and the user paid two clicks for one decision. Landing on
     a sparse, left-aligned screen (`items-start`) whose button repeats the
     label you just pressed reads exactly like a regression to an older build,
     which is how it was reported.
     The brief's actual concern was AUTO-START: the earlier behaviour opened a
     session the moment the app loaded, with no choice at all. The dashboard
     CTA already IS the deliberate choice. A confirmation screen behind a
     deliberate click is not consent, it is a second click.
     Note docs/08 never specified a gate screen (zero mentions); it was an
     over-reading of the brief, not a design-doc requirement, so removing it
     diverges from no binding design decision.
     CHANGE: Phase loses 'gate' and starts at 'answering'; SessionGate.tsx is
     deleted; the dashboard CTA keeps the "Enter sandbox" label as the single
     entry point. Auto-start remains impossible -- /session is only reached by
     an explicit navigation, never on login or app open, so the invariant the
     brief actually cared about is untouched.
     ALSO REMOVED: the Session screen's getMeStats() call. It existed solely to
     feed the gate's streak count, so it is now dead. This deletes the fetch
     that D-106/D-108 had to make best-effort precisely BECAUSE it could blank
     the core loop; the safest version of that call is the one not made. The
     streak still shows on Reveal and SessionComplete, from the attempt
     response, so no user-facing information is lost.
     TESTS: the three e2e specs that clicked the gate button (session,
     predict-the-fix, reveal-error-boundary) now assert the player opens
     directly. VERIFIED in a real browser, not just by typecheck: the hermetic
     predict-the-fix spec drives /session and lands straight in the answer UI
     (passing); dashboard-resilience and onboarding-gate pass, so the dashboard
     CTA and the onboarding redirect are intact; tsc --noEmit clean.
     NOTE (pre-existing, not fixed here): onboarding-gate.spec.ts:51 hardcodes
     `localhost:5173` in a toHaveURL assertion instead of deriving it from
     baseURL, so it fails on any other port even though the app is fine.

D-112 DATABASE_URL is normalised in code, not by hand. Preparing the backend
     for a managed Postgres (Neon) surfaced a first-boot failure that no test
     covered: every managed provider hands out a libpq URL, e.g.
       postgresql://u:p@ep-x.us-east-1.aws.neon.tech/neondb
         ?sslmode=require&channel_binding=require
     and SQLAlchemy's asyncpg dialect forwards EVERY query param straight to
     asyncpg.connect() as a keyword argument (create_connect_args does a bare
     `opts.update(url.query)`, no translation whatsoever). asyncpg has no
     `sslmode` kwarg and no `channel_binding` kwarg, so that URL is
       TypeError: connect() got an unexpected keyword argument 'sslmode'
     raised from inside the connection pool on the first request. The old
     sqlalchemy_database_url() made this WORSE, not better: it rewrote the
     scheme to +asyncpg and ignored the query string, so the URL looked
     handled right up until it wasn't.
     The alternative was to make the operator hand-convert the string on every
     deploy. Rejected: a deploy that depends on editing a connection string by
     hand is a deploy that breaks at 2am, and the failure mode is a stack trace
     that names neither the URL nor the offending param.
     CHANGE: normalize_database_url(url) -> (url, connect_args) in app/db.py is
     now the single door. It (1) accepts postgres://, postgresql:// or an
     already-correct postgresql+asyncpg:// and always emits +asyncpg;
     (2) translates sslmode/ssl into a connect_args["ssl"]; (3) DROPS query
     params asyncpg cannot accept, logging each one by name rather than failing
     opaquely; (4) disables BOTH statement caches when the host is a
     transaction pooler. create_engine(), alembic/env.py and main.py's healthz
     probe all feed from it, so `alembic upgrade head`, the app and the health
     check can never disagree about a URL.
     THE TRAP IS WORSE THAN IT LOOKS, and this is what settles the question:
     main.py's _check_postgres() did `asyncpg.connect(settings.DATABASE_URL)`,
     handing the env var straight to asyncpg as a DSN. asyncpg's DSN parser
     accepts libpq's sslmode/channel_binding happily, but rejects the driver
     outright: `invalid DSN: scheme is expected to be either "postgresql" or
     "postgres", got 'postgresql+asyncpg'`. So the two code paths have EXACTLY
     OPPOSITE requirements -- the engine needs +asyncpg and dies on sslmode,
     the probe dies on +asyncpg and accepts sslmode -- and therefore NO single
     string in DATABASE_URL satisfies both. Verified both directions. Asking
     the operator to hand-convert the URL was never merely fragile; it was
     impossible, and the failure was silent, because _collect_failures()
     records only a failed check's NAME and swallows the exception. The symptom
     would have been readiness pinned red forever with nothing saying why.
     _check_postgres() now builds its kwargs from asyncpg_connect_kwargs(),
     which routes through the same normalizer, so the probe tests the
     connection settings the app actually runs with.
     ALEMBIC WAS DISABLING APP LOGGING: alembic/env.py called
     fileConfig(config.config_file_name), whose disable_existing_loggers
     defaults to True. That disables every logger already imported in the
     process -- i.e. all of `app.*`. It is why the dropped-param warning above
     tested as silent, and it would have silenced it in any process that loaded
     Alembic first. Now passes disable_existing_loggers=False.
     WHY AN ALLOWLIST, NOT A DENYLIST: the set of params to keep is derived at
     runtime from inspect.signature(asyncpg.connect), not hardcoded. A
     hardcoded denylist of libpq params is wrong the day a provider adds a new
     one, and it is wrong silently -- in the same TypeError-at-first-connect
     way this entry exists to kill. Consistent with the response-schema rule in
     CLAUDE.md: allowlists, never denylists.
     SSL DEFAULT IS verify-full FOR REMOTE HOSTS: a URL with no sslmode whose
     host is a dotted FQDN gets ssl.create_default_context() (check_hostname=
     True, verify_mode=CERT_REQUIRED, OS trust store). Two reasons. First, the
     obvious hand-written form `?ssl=require` yields check_hostname=False and
     verify_mode=CERT_NONE -- encrypted, but any MITM presenting any
     certificate is accepted, over the public internet. Second, the intuitive
     fix `?sslmode=verify-full` does NOT work as a bare string: asyncpg goes
     looking for ~/.postgresql/root.crt and raises ClientConfigurationError
     when it is absent, which it always is in a container. Real verification is
     only reachable through connect_args, which is exactly why connect_args had
     to exist. An explicit sslmode in the URL is always honoured, so
     `?sslmode=require` still downgrades to encrypt-only on request.
     LOCAL IS UNTOUCHED: "local" = a loopback IP or a host with no dot in it,
     which covers localhost, CI, and docker-compose service names (`postgres`).
     Managed providers are all dotted FQDNs. A local URL with no sslmode gets
     no `ssl` connect_arg at all, so compose and CI keep connecting exactly as
     before. This is the reason for the no-dot rule rather than a plain
     localhost check: `postgresql://...@postgres:5432/...` in docker-compose.yml
     would otherwise have started demanding TLS from a container that has none.
     POOLER: Neon's -pooler host is PgBouncer in transaction mode, which hands
     each transaction a different backend, so a prepared statement made on one
     is gone on the next (InvalidSQLStatementNameError: prepared statement
     "__asyncpg_stmt_1__" does not exist). BOTH caches must die: asyncpg's own
     (statement_cache_size, a connect_args kwarg) and SQLAlchemy's dialect
     cache (prepared_statement_cache_size, a URL param). Killing only one -- the
     common half-fix -- still fails. Detected from the host (-pooler./.pooler./
     pgbouncer) or an explicit ?pgbouncer=true.
     REDIS NEEDED NO CHANGE, and this was verified rather than assumed:
     redis.asyncio's Redis.from_url() maps the rediss:// scheme to
     SSLConnection natively, so an Upstash URL drops into core/redis.py as-is.
     A test pins that so nobody "helpfully" adds TLS plumbing later.
     NOT CHANGED: config.py still types DATABASE_URL as a plain str. Validation
     belongs at the one place that builds an engine, and main.py's lifespan
     calls create_engine() at startup, so a bad URL still fails at boot rather
     than on first request.

D-113 backend depends on `fastapi[standard]`, not bare `fastapi`. The FastAPI
     Cloud deploy BUILT cleanly and then died at RUNTIME with
       RuntimeError: To use the fastapi command, please install
       "fastapi[standard]": pip install "fastapi[standard]"
       File "/app/.venv/bin/fastapi", line 10, in <module>
     FastAPI Cloud starts the app with the `fastapi` CLI (`fastapi run`). That
     CLI is packaged separately, as fastapi-cli, and is pulled in ONLY by the
     `standard` extra. backend/pyproject.toml asked for bare `fastapi`, so the
     deployed venv had the library but not the command that launches it.
     WHY IT WAS BARE, and why that looked fine: docker-compose runs the app with
     an explicit `uvicorn app.main:create_app --factory` command, never through
     the CLI, so uvicorn was pinned directly and the CLI was never missed. Local
     dev, CI and the container all exercised the uvicorn entrypoint. Nothing in
     the repo exercised the entrypoint the production host actually uses, which
     is why a build-green deploy could still be a runtime crash.
     CHANGE: 'fastapi>=0.115,<1.0' -> 'fastapi[standard]>=0.115,<1.0'. Same
     version constraint; the extra is additive.
     uvicorn[standard] IS DELIBERATELY KEPT, even though fastapi[standard] pulls
     uvicorn in transitively. docker-compose.yml invokes uvicorn by name, so it
     is a first-class dependency of the local stack, not an incidental one.
     Dropping it would make compose depend on a transitive package -- fine until
     the day the extra's contents change under us.
     RESOLUTION VERIFIED, not assumed: a full resolve of the dependency set with
     the extra applied yields 67 packages and no conflicts. Every existing pin
     still resolves inside its declared range (uvicorn 0.51.0 in >=0.34,<1.0;
     httpx 0.28.1 in >=0.28,<1.0; pydantic-settings 2.14.2 in >=2.7,<3.0; redis
     5.3.1 in >=5.2,<6.0). New arrivals are fastapi-cli (the actual fix),
     fastapi-cloud-cli, fastar, jinja2, python-multipart, email-validator,
     pydantic-extra-types, rich-toolkit and typer.
     LOCAL DEV IS UNBROKEN, and this was checked in the real container rather
     than reasoned about: the api image rebuilds, GET /healthz returns 200, and
     `fastapi --version` now answers inside the image (0.0.29) where it
     previously would not have existed. Backend suite: 427 passed, unchanged.
     NOT A D-112 PROBLEM. This is an entrypoint/packaging defect and shares no
     cause with the DATABASE_URL work; recorded separately so the two are not
     conflated when someone reads back the deploy history.

D-114 The frontend is served same-origin with the API, via a Vercel rewrite.
     The MVP splits the deploy across two hosts: the API on FastAPI Cloud
     (codereader.fastapicloud.dev) and the SPA on a static host. The obvious
     wiring -- SPA on *.pages.dev calling the API on *.fastapicloud.dev --
     cannot log in, and fails silently.
     WHY: the `rt` refresh cookie is SameSite=Lax (auth/router.py
     _refresh_cookie_kwargs). Lax sends a cookie cross-site ONLY on top-level
     GET navigations, never on a cross-site fetch. auth-context.tsx boots by
     POSTing /v1/auth/refresh. Two different registrable domains makes that a
     cross-site POST, so the browser withholds `rt`, refresh 401s, and the app
     lands back on /login rendering "Sign-in failed." No CORS error, no console
     warning -- CORS is already correct (allow_credentials=True, APP_ORIGIN in
     allow_origins) and the client already sends credentials:'include'. Nothing
     rejects the request; the cookie is simply never attached. This works on
     localhost only because :5173 and :8000 are the same site (port is not part
     of "site").
     REJECTED: SameSite=None; Secure. It works, on Chrome. It makes `rt` a
     third-party cookie, which Safari has blocked outright since 2020, Firefox
     partitions under Total Cookie Protection, and Chrome itself blocks in
     Incognito. Shipping a daily-habit PWA that cannot log in on any iPhone, to
     save a config file, is not a trade -- and the eventual fix would be this
     same change, made later with users already on it.
     REJECTED: custom domain with app./api. subdomains. Correct, and strictly
     the cleanest (same site, no proxy hop, Lax unchanged). Deferred only
     because it costs a domain purchase and DNS setup, and it is not mutually
     exclusive with this: moving to it later changes DNS and two env vars, not
     the auth model.
     CHANGE: frontend/vercel.json rewrites /v1/* to the FastAPI Cloud origin.
     The browser then only ever talks to the Vercel origin. The backend's
     Set-Cookie carries no Domain attribute, so `rt` lands host-only and
     FIRST-PARTY on the Vercel host, and SameSite=Lax is not merely tolerable
     but correct. No third-party cookie exists anywhere in the flow, so Safari,
     Firefox and Incognito all work. CORS becomes moot (same-origin, no
     preflight). No change to the cookie flags, to tokens.py, or to CORS.
     VITE_API_BASE_URL is set to the EMPTY STRING in frontend/.env.production
     (committed; it holds no secret), making every fetch a same-origin relative
     path. Empty string, NOT "/": api.ts uses `?? `, which only falls back on
     null/undefined, so '' survives -- while "/" would build "//v1/auth/refresh",
     a protocol-relative URL pointing at a host named `v1`.
     GITHUB_REDIRECT_URI and APP_ORIGIN must both name the VERCEL origin, not
     the FastAPI Cloud one. The OAuth callback has to return THROUGH the proxy,
     or the backend sets `rt` on fastapicloud.dev and the bug is back.
     SERVICE-WORKER TRAP, found before it bit: vite-plugin-pwa defaults to
     workbox navigateFallback: 'index.html'. /v1/auth/github/start is now a
     same-origin top-level navigation (the login link), so the SW would have
     served the SPA shell instead of letting it reach the proxy, and OAuth would
     never start. vite.config.ts now sets navigateFallbackDenylist: [/^\/v1\//].
     KNOWN LIMIT: preview deployments get unique *.vercel.app subdomains and a
     GitHub OAuth app has one fixed callback URL, so OAuth only works on the
     production URL. Previews render but cannot log in. True of the custom-domain
     route too; not introduced by this decision.

D-115 The soft-launch ships spot_the_bug + trace + predict_the_fix; summarize is
     built but OFF. docs/03 and docs/01 still describe the MVP type set as
     spot_the_bug + trace + summarize, and docs/03 puts summarize inline grading
     in scope. That is now stale. Reality (verified in code): sessions/sampler.py
     DETERMINISTIC_TYPES = (spot_the_bug, trace, predict_the_fix); summarize is in
     ALL_CANDIDATE_TYPES but is not sampled into the shipped set, and the pipeline
     generates predict_the_fix (publish.py).
     WHY: summarize is the only type with a per-answer LLM cost and the only one
     that puts a rubric/grader on the hot path (a prompt-injection surface and a 6s
     timeout). predict_the_fix is deterministically graded (grading.py
     DETERMINISTIC_TYPES) with ground truth from the sandbox: every distractor fix
     is executed and must still fail the test. So dropping summarize and adding
     predict_the_fix removes all per-answer LLM cost and the injection surface while
     keeping three types. predict_the_fix was a post-MVP flagship in docs/00; it is
     now shipped.
     CHANGE: HANDOFF.md already reflects this. docs/03 and docs/01 are corrected by
     pointer to this entry rather than rewritten, since 03 is a historical MVP-scope
     doc. If summarize is ever turned back on, that is a new decision, not a revert.
D-116 A "covered day" is the single currency of streak protection, and it is
     read from the streak_events ledger, not from the freeze balance. docs/10's
     A1 spec states consumption as a pure balance rule ("a gap of N missed days
     and streak_freezes >= N and N <= STREAK_FREEZE_MAX -> consume N"), and
     separately promises that an outage freeze fills a day "WITHOUT spending
     their balance". Those two rules contradict each other the moment both
     mechanisms touch one gap. Under the balance-only rule, a user whose single
     missed day was already filled by an ops outage-freeze still needs
     streak_freezes >= 1 to survive that gap, so a user with a zero balance
     loses the streak the outage was declared to protect. The outage promise is
     the stronger one: it is an apology for our downtime, and it cannot be
     payable only by users who happen to hold currency.
     RESOLUTION: on a gap, compute the missed local dates (strictly between
     last_active_local_date and today). A missed date is COVERED if a
     freeze_used row already exists for (user_id, that_date), whatever wrote it.
     uncovered = missed dates with no such row. The balance pays only for
     uncovered, and both the balance test and the STREAK_FREEZE_MAX cap apply to
     len(uncovered), never to total gap size. Outage-covered days are therefore
     free and do not consume the cap. A duplicate freeze_used is never written
     for a date that already has one, which makes the fill idempotent and makes
     the ledger, not a counter, the source of truth. All-or-nothing is preserved
     exactly as specified: if len(uncovered) exceeds min(streak_freezes,
     STREAK_FREEZE_MAX) the gap falls through to the existing reset unchanged and
     no freeze is spent. A freeze never partially covers a gap.
     WHY the ledger and not a counter: freeze_used rows are already immutable
     audit rows under invariant 5, they are already keyed by local_date, and the
     partial unique index deliberately excludes them, so they can be backfilled
     by ops for a past date without colliding. That makes them the only record
     that both mechanisms can agree on. A separate "outage days" table or a
     nullable flag on user_stats would be a second source of truth for the same
     fact.
     CONSEQUENCE, accepted: the outage endpoint becomes a pure ledger write. It
     never mutates current_streak and never manufactures a streak, because
     protection is realized lazily at each user's next submit. A user who was
     already inactive for a week before the outage day has one of seven missed
     days covered, so they still reset. This is why the endpoint is safe to run
     over every user with recorded activity rather than a hand-picked cohort.
     THREE DIVERGENCES from docs/10's A1 spec, found in code and recorded here
     rather than silently worked around:
     (a) docs/10 says to "mirror streak_recon.py's bulk pattern" for the outage
     endpoint. There is no bulk pattern there. jobs/streak_recon.py is not a job
     and is not registered in jobs/runner.py: it is a single-user, single-row
     helper called synchronously from PATCH /me, operating on a User handed to
     it, and it never commits (users/service.py owns the transaction). It has
     nothing bulk to copy. The outage endpoint is instead written as one
     set-based INSERT ... SELECT ... WHERE NOT EXISTS, which gets the skip-
     existing-rows rule from D-116 above for free and holds no per-user state.
     What IS reused from streak_recon.py is its EVENT convention: from_value ==
     to_value when a row records bookkeeping rather than a streak change.
     (b) docs/10 says to extend the stats payload to expose streak_freezes and
     repair_available. streak_freezes is ALREADY exposed (users/service.py
     get_stats, both the empty-stats and real branches). AMENDED: the allowlist
     gains TWO new keys, repair_available and repair_restores_to (int|null).
     repair_available alone cannot render the specified affordance copy
     "Restore your N-day streak" -- N is the restorable value, which is derived
     from the ledger and appears nowhere else in the payload. Shipping the
     affordance without N would mean either a vaguer button or a second
     round-trip. Both keys are computed per request and never stored, and
     repair_available is exactly (repair_restores_to is not None), so the two
     can never disagree; a test asserts the advertised N equals the value the
     repair actually writes.
     (c) event='repaired' is ALREADY WRITTEN by streak_recon.py for the timezone
     boundary case, so "a later repaired row disqualifies this reset" would let
     an unrelated timezone change silently consume a user's one repair. Repair
     rows written by POST /v1/streak/repair therefore carry an explicit anchor
     marker in `note` ("[repair:anchor=<reset streak_events.id>]") and the
     one-shot check matches only on that marker. The anchor is the reset row's
     primary key, so the check is exact rather than time-window heuristic.
     ALSO: the restore value is computed from the ledger (reset.from_value +
     (today - reset.local_date).days), never from current_streak, which may have
     been mutated by submits made after the reset.
     NOT CHANGED: no migration, no schema change. The partial unique index
     uq_streak_events_one_transition_per_day is WHERE event IN
     ('extended','reset'), so freeze_used/repaired/adjusted rows are unconstrained
     and backfill cleanly; the CHECK already allows all five event kinds; and
     user_stats.streak_freezes already exists. D-19 (one submission = one day,
     correctness-independent) is untouched: no XP or goal threshold enters the
     streak.

D-117 CLOSED. Both .env.example files are drift-checked, each against its own
     contract. backend/tests/test_env_example.py used to walk UP from its own
     path and validate the FIRST .env.example it found, which is
     backend/.env.example. The root .env.example was therefore never validated
     by anything and could drift silently. Found while adding the A1 knobs:
     updating only the root file left the suite red (the good failure), while
     updating only the backend file would have left the root file stale with NO
     failure (the bad one, and the actual hazard).
     THE ROOT FILE HAD ALREADY DRIFTED. Closing this immediately caught it: the
     root .env.example was missing VALIDATION_REPORTS_DIR, a PipelineSettings
     knob, and nothing had noticed. That is the whole argument for closing it
     rather than deferring.
     The two files are NOT duplicates and do not share a contract:
       backend/.env.example -> exactly Settings
       root/.env.example    -> Settings PLUS PipelineSettings (the shared file;
                               backend knobs are mirrored into it so it stays
                               drift-free against the pipeline, D-44/D-80)
     REJECTED: deleting the root file. It is the shared pipeline+backend file
     and carries 9 pipeline-only knobs the backend file has no business
     holding. REJECTED: pointing the walk-up loop at the root file instead;
     that just swaps which file drifts unchecked.
     CHANGE: three tests -- both files exist (so deleting one is a deliberate
     edit, not a silent weakening), backend == Settings, root == Settings |
     PipelineSettings. Both files carry the four STREAK_* knobs.

D-118 Existing soft-launch users get a ONE-TIME backfill of the A1 starting
     freeze balance. user_stats rows created before A1 sit at streak_freezes = 0
     because the DB default is 0 and the STREAK_FREEZE_START grant happens at
     row CREATION (streak/service.py new_user_stats). So new signups would start
     with 2 while every existing soft-launch user starts with 0 and waits up to
     10 active days for their first freeze.
     WHY BACKFILL RATHER THAN LET IT AGE OUT: the soft-launch cohort is the only
     cohort we have, and it is exactly the audience A1 was built for. Shipping a
     safety net that protects future users but not current ones inverts the
     point of the phase (docs/10: "retention of already-active users is the
     growth lever"). The aging-out path also means the users most likely to miss
     a day -- busy professionals in their first weeks -- are the ones with no
     protection.
     REJECTED: raising the DB default to 2. It would not touch existing rows, so
     it fixes nothing here, and it would silently re-grant on any future row
     recreation. The grant belongs in one place, at creation, plus this explicit
     one-time catch-up.
     REJECTED: granting lazily on next submit if balance == 0. It cannot
     distinguish "never granted" from "granted and legitimately spent", so it
     would hand a free freeze to every user who ever used theirs. That is an
     infinite freeze supply, not a backfill.
     CHANGE: POST /admin/streak/grant-initial-freezes { local_date } behind the
     existing admin auth, mirroring the outage-freeze shape (one set-based
     statement, no per-user state). Sets streak_freezes to min(START, MAX) for
     users below it, never lowers a balance, never touches current_streak, and
     writes one `adjusted` row per granted user carrying the marker
     [a1:initial-grant] so the ledger explains the balance.
     IDEMPOTENT ON TWO INDEPENDENT GUARDS, both required. The balance test
     (streak_freezes < grant) skips anyone already topped up. The ledger-marker
     test skips anyone already granted, and it is the one that matters on a
     re-run months later, when a granted user may have legitimately spent down
     to 0 and the balance test alone would cheerfully re-grant them. A negative
     test covers exactly that case.
     RUN IT ONCE after deploy; re-running is a no-op that reports granted_to: 0.

D-119 frontend/e2e/session.spec.ts is KNOWN-FAILING and NOT ROOT-CAUSED. Marked
     test.fixme rather than left red. Verified to fail identically on master
     (67cf7b8), so A1 did not cause it.
     SYMPTOM: against a healthy local stack, the seeded user's dashboard already
     reads "Completed" (1/5, 1 skipped) before the spec finishes driving the
     session, so /session redirects to the dashboard and the spec's first
     locator (`span.capitalize`, the exercise-type label) is never found. It
     fails 15s later on that selector, which points at the UI and not at the
     cause.
     WHAT IS NOT THE CAUSE, checked: the seeding path is fine
     (reveal-error-boundary.spec.ts uses the same seeded setup and PASSES
     against a healthy stack); the selector still exists (Session.tsx); and it
     is not the missing Playwright webServer, which was a separate real bug
     fixed alongside this.
     WHAT IS UNKNOWN: whether this is spec brittleness (it drives "one of each
     type" while summarize is OFF per D-115, and only 1 summarize row is live)
     or a genuine early-completion bug in the session flow. Guessing was
     declined; a wrong fix here would paper over a possible product bug.
     WHY test.fixme AND NOT test.skip: fixme reports as skipped but means "needs
     fixing", so it stays visible in the suite output. The alternative -- leaving
     it red -- trains everyone to ignore a red suite, at which point the suite
     stops being a signal at all. The alternative of a plain skip would let it
     disappear.
     TO PICK IT UP: delete the `test.fixme(...)` line at the top of the spec.
     Start by checking whether the session is being marked completed early for a
     freshly seeded user, since that is the observed state and it is the part
     that could be a real bug.

     CORRECTION (2026-07-18, found while building A2). One factual claim above
     is WRONG and the reasoning that rests on it is weaker than it reads.
     D-119 says reveal-error-boundary.spec.ts "uses the same seeded setup and
     PASSES against a healthy stack", and uses that as the evidence that the
     seeding path is fine and the fault is specific to session.spec.
     reveal-error-boundary.spec.ts is in fact FLAKY: measured at roughly 2 of 5
     runs failing against a healthy local stack, both in a full-suite run and
     run in isolation, and it fails on the SAME selector at the same line
     (`span.capitalize`, the exercise-type label, spec line 49) with the same
     "element(s) not found" shape.
     So the early-completion condition is NOT specific to session.spec. It
     affects at least two seeded specs and is intermittent rather than
     deterministic, which points harder at a real race in session
     creation/completion for a freshly seeded user than at spec brittleness.
     The D-119 hypothesis "it drives one of each type while summarize is OFF"
     does not explain this spec at all, since this one does not do that.
     NOT FIXED HERE, deliberately: A2 is email capture, this is a session-flow
     bug, and D-119's own reason for not guessing still stands. Recorded rather
     than absorbed because the next person to pick up D-119 would otherwise
     start from a premise that is not true. Do not mark this spec fixme without
     investigating: unlike session.spec it passes most of the time, so it still
     carries real signal.

     ROOT-CAUSED (2026-07-18). It is a real concurrency bug in session creation,
     NOT spec brittleness and NOT a D-58..D-62 "transient empty session"
     regression. Session creation is healthy: 20 consecutive freshly seeded
     users, driven over plain HTTP with no browser, returned 5 exercises and
     completed=false every single time (20/20, zero empties, zero non-200s).
     THE CHAIN, from the API log of a failing run:
       1. The SPA issues TWO concurrent GET /v1/session/today for the same
          first-of-day user. This is React 18 StrictMode double-invoking
          Session.tsx's mount effect (main.tsx wraps the app in StrictMode).
          Confirmed in the log: every run shows two GETs from two source ports.
       2. Both find no daily_sessions row, both sample, both INSERT. One wins.
          The loser gets
            UniqueViolationError: duplicate key ... "daily_sessions_pkey"
            Key (user_id, session_date)=(<uuid>, 2026-07-18) already exists
          raised at sessions/service.py:147 (`await db.flush()`).
       3. The IntegrityError handler at :149 EXISTS and its intent is right
          (roll back, re-read the winner's row, D-17). It is the RECOVERY that
          fails: `await db.get(...)` at sessions/service.py:153 raises
          sqlalchemy.exc.MissingGreenlet from the connection-pool checkout's
          pre-ping (db.py:234 sets pool_pre_ping=True). The handler written to
          absorb this race is itself the thing that 500s.
       4. The MissingGreenlet escapes as an UNHANDLED ASGI exception, so the
          500 is emitted WITHOUT CORS headers. The browser's fetch therefore
          rejects at the network layer instead of parsing an error body, and
          api.ts maps it to `network_error`. The screen shows "Could not reach
          the server. Check your connection." (confirmed verbatim in the
          Playwright error context). `span.capitalize` never renders, which is
          the reported symptom and is four steps downstream of the cause.
     WHY D-119's ORIGINAL DIAGNOSIS MISSED IT: the observed state was read as
     "the dashboard already says Completed", but the session is never completed
     and never empty. The failing screen is the session player's LOAD-ERROR
     branch, not a redirect and not the empty-session branch.
     SEVERITY, stated carefully. The TRIGGER is dev-only: StrictMode
     double-invokes effects only in development builds, so a production SPA
     fires one request per mount. The BUG is not dev-only: any genuine
     concurrency on a user's first request of the day reaches the same path
     (two tabs, a double-click, a reload mid-flight), and the recovery is broken
     for all of them. It is the first-of-day window only, which is exactly the
     path every new beta user takes exactly once.
     MEASURED RATE: 11 of 15 failures (73%) run back-to-back with no pacing;
     roughly 1 in 3 when runs are spaced. The rate tracks how tightly the two
     requests land, which is what a race should look like.
     STILL UNPROVEN, and worth confirming before fixing: precisely WHY pre-ping
     raises MissingGreenlet on the post-rollback checkout rather than completing
     normally. The escape to a 500 is proven; the SQLAlchemy internals behind
     that specific checkout are not, and a fix aimed at the wrong layer (for
     example "catch MissingGreenlet") would paper over it.
     CANDIDATE FIXES, NOT APPLIED, pending a scope decision: make the insert
     conflict-proof at the DB (ON CONFLICT DO NOTHING, then read) so the
     recovery path is never entered; and/or take the per-(user, day)
     pg_advisory_xact_lock that D-104 already established for attempts, which is
     the consistent-with-precedent option. Separately, the unhandled-exception
     path should carry CORS headers either way: a 500 the browser cannot read as
     a 500 will keep producing misleading "network error" symptoms in any future
     incident.
     NOTE FOR session.spec.ts (still test.fixme): it very likely shares this
     root cause, but that is NOT verified. Re-check it after this is fixed
     rather than assuming it is resolved.

     CLOSED (2026-07-18). Both halves are now resolved and this entry is done.
     The session-build race was D-122. The session.spec.ts half is below, and it
     was NOT the same bug and NOT a product bug at all.
     ROOT CAUSE: the spec asserted a "Session complete" screen. There is no such
     screen anywhere in frontend/src, and its absence is a deliberate, recorded
     decision (HANDOFF and docs/10: Session.tsx redirects to the Dashboard once
     the last exercise is answered; building a real session-complete screen is
     its own deferred piece of work). So the loop's break condition could never
     fire, the run walked one iteration past the last exercise, /session had
     already redirected to the Dashboard, and `span.capitalize` was missing. The
     failure surfaced on a selector four steps from the actual mistake, which is
     the same shape of confusion D-121 describes and the reason both took so
     long to see.
     MY EARLIER READING WAS WRONG, and it is worth naming because it sent the
     next round of investigation down a false path. I read the dashboard's
     "1/5, 1 skipped" as "one of five attempted" and wrote that into this entry
     as evidence of early completion. It is correct_count/exercise_count
     (Dashboard.tsx:203): ONE CORRECT out of five, in a session that had
     finished. The browser log shows five POST /v1/attempts against a five-slot
     session. Nothing ever disagreed: a direct measurement showed 5 slots
     persisted and 5 exercises served, both before and after attempts.
     HYPOTHESIS TESTED AND REJECTED: that GET /v1/session/today served fewer
     exercises than daily_sessions held slots. Measured directly and it does
     not: persisted == served == 5, and the served slate does not shrink as
     exercises are answered.
     SEVERITY: NOT test-only, and NOT production-reachable either, because there
     is no defect in the product. The version of this that WOULD have been
     serious -- a real user told they are finished partway through -- is not
     reachable, and that is now pinned by tests rather than by argument
     (test_d119_session_completion.py). A pool too small for the sampler's usual
     3-to-5 slots yields a SHORT session, not a dishonest one: served count
     equals persisted count, `completed` turns true only once every served
     exercise has been attempted, and a skip counts as an attempt (D-19/D-93) so
     a skipped slot cannot strand the session. Those three are the invariants
     that matter for the daily loop, and they hold.
     FIX: in the spec, asserting the completion signal this app actually has --
     the redirect to the Dashboard plus its completed state and review link. The
     loop now bounds on leaving /session rather than on a screen that does not
     exist, so a 3, 4 or 5 exercise session all pass equally.
     Also fixed the same dead expectation in reveal-error-boundary.spec.ts,
     where `.or(getByText('Session complete'))` was harmless only because the
     other branch always matched; had the session actually ended there it would
     have failed for an invented reason.
     PROVED TO THE D-122 STANDARD: 8 of 8 failing before, 12 of 12 passing
     after, and the test.fixme is removed so the spec runs for real again.

D-120 A2 email capture. Six decisions, recorded before any code was written.
     This is the FIRST PII in the system, so each one is written down with the
     attack or failure it is defending against, not just the shape it produces.

     (1) EMAIL IS CAPTURED IN-APP, NOT BY WIDENING THE OAUTH SCOPE. GitHub OAuth
     stays at `read:user` (auth/oauth.py:60). Widening to `user:email` would hand
     us a verified address for free and is the obvious move, and we are declining
     it for two reasons. First, scope is the thing a developer audience actually
     reads on the GitHub consent screen, and `read:user` is defensible at signup
     in a way that "and your email addresses" is not, on an app whose entire
     pitch is trust. Second, and decisively: changing the requested scope forces
     RE-CONSENT for every existing soft-launch user. They would be bounced back
     through an authorization screen to grant something the product did not need
     when they joined. An in-app prompt asks the same question at a moment the
     user has context for it ("add email for reminders and your weekly recap")
     and costs nothing to anyone who says no.
     CONSEQUENCE, accepted: our address is self-asserted, so it MUST be verified
     by us. Hence (2) and (4). A `user:email` address would have arrived
     pre-verified by GitHub; this is the price of the narrower scope.

     (2) CHANGING AN EMAIL DOES NOT TAKE THE OLD ONE OFFLINE. `users.email` holds
     ONLY a verified address. A newly submitted address lands in
     `users.pending_email` and stays there until its token is consumed, at which
     point pending is promoted into `email`, `email_verified_at` is stamped, and
     `pending_email` is cleared. Until then the previously verified address keeps
     working.
     WHY: a typo must not silently destroy the notification channel. The failure
     being prevented is concrete: a user with a working address types
     `me@gmial.com`, we overwrite `email`, the verification mail goes nowhere,
     and the user is now unreachable AND unaware, because from their side the
     profile shows the address they meant to type. Under this rule the mistake is
     self-correcting: the old address still receives, and the pending one visibly
     never confirms.
     SECOND REASON, forward-looking: A3 (reminders, weekly recap) must never have
     to reason about deliverability. Under this rule A3 reads `users.email` and
     sees either an address we have proven we can reach, or NULL. There is no
     third state, so A3 needs no "is this one actually good" check and cannot
     send to an unverified address by construction.
     CONSEQUENCE: first-ever capture also goes through `pending_email`, not
     straight into `email`. Uniform path, one state machine, no special case for
     "user had no address before".

     (3) UNIQUENESS IS PARTIAL, AND DELIBERATELY DOES NOT COVER PENDING OR
     UNVERIFIED ADDRESSES:
       CREATE UNIQUE INDEX uq_users_email_verified ON users (email)
         WHERE email_verified_at IS NOT NULL AND deleted_at IS NULL;
     Mirrors the uq_streak_events_one_transition_per_day pattern (D-116 era):
     partial, SQL-only, not declared on the model.
     WHY NOT A PLAIN UNIQUE ON `email`: it would be an ADDRESS-SQUATTING PRIMITIVE.
     An attacker types a victim's address into their own profile, never verifies
     it, and the row now blocks the victim from ever registering it. The victim
     cannot clear it, cannot see it, and support cannot distinguish the squat
     from a legitimate typo. Uniqueness must therefore attach to PROVEN control
     of an address, not to the act of typing one, and proof is exactly
     `email_verified_at IS NOT NULL`.
     `deleted_at IS NULL` is in the predicate so a soft-deleted account does not
     tombstone its address forever; users are the one soft-deleted table
     (docs/04), so every unique index over them has to say this.
     CONSEQUENCE, accepted: two live rows may hold the same string in
     `pending_email` at once, and a race can let two users both hold verification
     tokens for one address. That is fine and is the correct outcome: whichever
     one verifies FIRST wins the partial index, and the second one's promotion
     then fails the constraint and is reported to that user as a generic failure
     per (5). The database is the arbiter, not an application-level pre-check,
     which would be a TOCTOU hole anyway.

     (4) TOKENS: HASHED AT REST, SINGLE-USE, EXPIRING, AND SCOPED TO ONE ADDRESS.
     MATCHED EXACTLY TO THE EXISTING REFRESH-TOKEN STORAGE, which is already
     hashed: auth/tokens.py:121-126 generates `secrets.token_urlsafe(32)` and
     stores `hashlib.sha256(token.encode()).digest()` as bytea. A2 reuses that
     pair verbatim rather than inventing a second scheme. Unsalted single-round
     SHA-256 is correct here for the same reason it is correct there: the input
     is 256 bits of CSPRNG output, not a password, so there is no dictionary to
     precompute and a KDF would buy nothing.
     NEW TABLE `email_verification_tokens`: user_id, the target `email` the token
     was issued FOR, `token_hash` bytea UNIQUE, `expires_at`, `consumed_at`,
     `invalidated_at`, `created_at`. Storing the target address on the TOKEN and
     promoting THAT value (not whatever `pending_email` says at consume time) is
     what makes the flow safe against a change-then-verify race: an old link can
     never promote a newer address it was not issued for. Issuing a new token
     stamps `invalidated_at` on the user's outstanding ones.
     DIVERGENCE FROM THE SPEC'D COLUMN LIST, deliberate: `invalidated_at` is an
     extra column, not one of the five specified. The alternative was DELETing
     superseded rows. Rejected: "why did my verification link stop working" is
     then unanswerable, and that is the same argument docs/04 makes for
     streak_events ("my streak vanished must be answerable in one query"). A
     ledger costs one nullable timestamptz.
     DIVERGENCE FROM THE REFRESH-TOKEN PATTERN, deliberate and a STRENGTHENING:
     refresh tokens are matched by DB hash equality (auth/service.py:201-203),
     which is not a constant-time comparison. That is defensible for refresh
     tokens and we are NOT changing it here, but A2 additionally runs
     `hmac.compare_digest` on the stored hash versus the recomputed hash after
     the lookup. Constant-time comparison of a token was an explicit requirement
     for this phase; the DB lookup narrows the row, the compare_digest is what
     the code actually branches on.

     (5) EVERY VERIFICATION FAILURE RETURNS ONE GENERIC RESPONSE. Unknown token,
     expired token, already-consumed token, invalidated token, a token belonging
     to another user, and a promotion that loses the (3) race all return the same
     status and the same body. Distinguishing them is an oracle: "already
     consumed" tells an attacker the token was real, and "belongs to another
     user" confirms an address is registered. Relatedly, POST /v1/me/email
     returns the SAME success response whether or not the target address is
     already verified on another account. The address either receives a mail or
     does not; the API never says which. Registration-status disclosure is the
     classic enumeration leak and there is no product reason to take it.

     (6) WHAT THE OWNER SEES ON GET /me: `email` (the verified address, or null),
     `email_verified` (bool), and `pending_email` (or null). All three are added
     to the `user_response` allowlist (auth/service.py:35-45), which is the same
     allowlist invariant 2 protects.
     WHY `pending_email` IS EXPOSED AT ALL: the pending state is unrenderable
     without it. "We sent a link to m****@example.com, resend?" requires the
     address, and the alternative (a bare boolean) produces a screen that cannot
     tell the user WHICH address to go check, which is precisely the typo case
     (2) exists to make visible. It is not a new leak vector: /me is strictly
     self-scoped by bearer token, and the value is a string the owner typed into
     this same screen minutes earlier. There is no path by which /me discloses
     any other user's address.
     WHY `email_verified` IS CARRIED SEPARATELY when it is, under (2), exactly
     `email is not None`: the client branches on verification, and making it
     infer that from the nullness of another field is the kind of implicit
     coupling that breaks silently the first time an unverified address can ever
     reach `email` (an import path, an admin tool). The redundancy costs one
     boolean and a test asserts the two can never disagree.
     NOT EXPOSED: `email_verified_at` (the timestamp is ops data, the boolean is
     the product fact) and anything from `email_verification_tokens`.
     ALSO NOT CHANGED: email does NOT go through PATCH /me. PATCH /me is a
     partial update that applies fields and returns; email needs issue-send-
     confirm semantics, a throttle, and a failure mode that is not "the field did
     not change". Four dedicated routes instead: POST /v1/me/email,
     POST /v1/me/email/verify, POST /v1/me/email/resend, DELETE /v1/me/email.
     DELETE exists because consent that cannot be withdrawn in-product is not
     consent; it clears email, email_verified_at and pending_email, and
     invalidates outstanding tokens in one transaction.

     NO BACKFILL. `users` has no email column today, so every existing row starts
     at NULL, which is the correct and intended "no email captured" state. This
     is the difference from D-118, which needed a backfill precisely because its
     column already existed with a wrong-for-the-cohort default.

D-121 An unhandled exception must reach the browser AS a 500: JSON body, uniform
     error shape, and CORS headers. Previously it did not, and that single gap
     corrupted two separate incident investigations.
     THE MECHANISM. `@app.exception_handler(Exception)` already existed and
     already produced a correct `{error: {...}}` body with security headers
     (M2). But an app-level exception handler is invoked by Starlette's
     ServerErrorMiddleware, which is the OUTERMOST layer, outside every user
     middleware including CORSMiddleware. So the 500 went out with no
     Access-Control-Allow-Origin, and a browser will not expose such a response
     to JS at all. The SPA therefore never saw a 500 with a readable body; it
     saw a rejected fetch, and api.ts mapped that to `network_error` ->
     "Could not reach the server. Check your connection."
     WHY THIS IS NOT COSMETIC. It is an error that disguises itself as a
     different, vaguer error, and every downstream diagnosis inherits the
     disguise. D-119 spent its whole first investigation treating a server-side
     race as a client/network/selector problem because that is what the browser
     was told. The incident report's mid-session "Something went wrong" is the
     same shape. A wrong error message is not a small bug when it is the only
     evidence anyone has.
     CHANGE: a `_catch_unhandled` HTTP middleware registered FIRST in
     create_app(), which makes it the INNERMOST user middleware (Starlette's
     add_middleware prepends, so last-added is outermost). It catches Exception,
     builds the response via a shared `_unhandled_response()`, and returns it --
     so the response travels back out THROUGH CORSMiddleware, which applies the
     headers itself. The app-level handler stays as the last-resort net for
     anything raised in the outer middlewares, where CORS is genuinely out of
     reach; both paths share one response builder so they cannot drift.
     REJECTED: setting Access-Control-Allow-Origin by hand in the error handler.
     It would mean echoing the request's Origin, which turns the 500 path into a
     CORS bypass for any origin on the internet. The allowlist must stay with
     the middleware that owns it. A negative test asserts a disallowed origin is
     still refused on the error path.
     REJECTED: moving CORSMiddleware to be outermost instead. It would fix this
     case but leaves the general rule ("responses generated above the CORS layer
     are invisible to the browser") intact and re-breakable by the next
     middleware anyone adds. Catching low is the structural fix.
     HANDOFF'S SECOND INSTANCE IS MISDIAGNOSED, and this is recorded rather than
     silently "fixed". HANDOFF says the mid-session failure is a 403
     `exercise_not_in_session` that "lacks an {error: ...} body". IT DOES NOT AND
     NEVER DID. It is raised as ApiError (attempts/service.py:407), gets the
     standard body from api_error_handler, and
     test_m4_attempts.py::test_attempt_on_exercise_not_in_session_returns_403 has
     asserted exactly that body since M4 and passes. There was nothing to fix.
     The far more likely real cause of that incident is this same CORS gap:
     POST /v1/attempts calls get_today_slots(), which is precisely the function
     that was 500ing under D-122, and a 500 there presented to the user as the
     generic catch-all. Not proven, so it is recorded as the leading hypothesis
     rather than a closed finding. A regression test now pins the 403's body and
     CORS headers so the claim cannot be re-derived from a bad memory.

D-122 First-of-day session creation is serialized by a per-(user, day) advisory
     lock. This closes the race root-caused under D-119.
     THE BUG: two concurrent GET /v1/session/today for a user with no
     daily_sessions row both found nothing, both sampled, and both INSERTed. The
     loser hit daily_sessions_pkey, and the IntegrityError recovery written for
     exactly this case then failed on its own re-read, so the request 500d (and,
     per D-121, that 500 reached the browser as a network error).
     CHANGE: `pg_advisory_xact_lock(hashtext(user_id), hashtext("session_build:" +
     date))` at the top of _build_and_persist_session, followed by a re-read of
     the row under the lock. D-104's lock class, third application (attempts,
     streak repair, now session build).
     DOUBLE-CHECKED, and that is the point of the re-read. The caller has
     already returned on a Redis hit or an existing row, so the hot path -- every
     request after the first of the day -- never reaches the lock and pays
     nothing for it. The re-read closes the window between the caller's check
     and the acquisition: the loser blocks until the winner commits, then READ
     COMMITTED hands it a fresh snapshot containing the winner's row, which it
     returns. Both callers therefore see the IDENTICAL session, which is a
     stronger guarantee than "no crash" and is asserted directly.
     Keyed per-(user, day), not per-user: the protected object is exactly one
     row per (user_id, session_date), and a per-user key would serialize
     unrelated days for no benefit.
     REJECTED: INSERT ... ON CONFLICT DO NOTHING then read. It is a smaller
     change and it would work, but it is a fourth distinct concurrency idiom in
     a codebase that has already standardised on this advisory lock in two
     places. Consistency here has real value: the next person reading
     sessions/service.py should find the same pattern they just read in
     attempts/service.py, not a new one to evaluate. ON CONFLICT also expresses
     "tolerate the collision" where the lock expresses "prevent it", and the
     sampling work done before the insert is wasted under the former.
     KEPT: the IntegrityError handler, now unreachable via the concurrent path,
     as the DB backstop underneath the lock -- the same relationship the partial
     unique index on streak_events has to the attempts lock (D-104).
     NOT FIXED, DELIBERATELY: the MissingGreenlet raised by that recovery path's
     `db.get` from the connection pool's pre-ping. It remains UNEXPLAINED and
     UNFIXED. Catching it would paper over the wrong layer, and it is now
     unreachable. If that branch ever fires again, that is evidence the lock was
     bypassed, not a licence to catch the symptom.
     PROVED BY REMOVAL, per the D-104 discipline. Reverting the lock makes
     test_d122_session_build_race.py fail with the exact production chain
     (UniqueViolationError on daily_sessions_pkey -> MissingGreenlet -> 500);
     restoring it makes both tests pass. End to end:
     reveal-error-boundary.spec.ts went from 11 of 15 FAILING to 15 of 15
     PASSING across consecutive runs.
     session.spec.ts (D-119) DOES NOT SHARE THIS CAUSE. It was re-checked
     against this fix rather than assumed: it failed 8 of 8, deterministically,
     which is a logic bug and not a race. It has since been root-caused and
     fixed separately (see D-119's CLOSED section): the spec asserted a
     "Session complete" screen that does not exist, so it was never a product
     bug at all. NOTE: an earlier version of this paragraph claimed the session
     "presents as finished after two of five exercises". That was wrong -- the
     dashboard's "1/5" is correct_count/exercise_count, so it means one correct
     in a FINISHED five-slot session. Corrected here rather than deleted,
     because that misreading is what made the remaining half look like a
     backend bug for longer than it should have.

D-123 summarize is OFF, and the switch now ENFORCES it. D-115 said summarize was
     off and claimed, "verified in code", that the sampler already excluded it.
     THAT CLAIM WAS FALSE. sessions/sampler.py's DETERMINISTIC_TYPES does exclude
     summarize, but sessions/service.py chose
       DETERMINISTIC_TYPES if degraded else ALL_CANDIDATE_TYPES
     so a HEALTHY grader pulled summarize into the candidate pool. The only thing
     standing between a user and a summarize exercise was the absence of live
     summarize content, which is not a control.
     FOUND BY USING THE APP, not by a test. A summarize exercise was served in a
     real local session and graded by a real OpenAI call.
     PRODUCTION WAS EXPOSED, and this is the part that matters: prod has ONE live
     summarize row and has had it throughout the soft launch, so a summarize
     exercise was samplable at any time. Measured at the same time: ZERO
     summarize attempts have ever been recorded in production, so no real user
     hit it, no LLM spend was incurred, and the injection surface was never
     exercised. Exposed but not hit. That is luck, not design: 1 live summarize
     row against 97 live deterministic rows, sampled into 3-5 slots.
     WHY IT MATTERS BEYOND ONE TYPE: summarize is the only type with a
     per-answer LLM cost and the only one that puts a grader on the REQUEST path,
     which is the prompt-injection surface invariant 6 exists for. Both of those
     were live in production for weeks on an unexercised path.
     CHANGE: new setting SUMMARIZE_ENABLED, default FALSE. The exclusion is
     applied to the SQL type filter in fetch_candidates, so it holds regardless
     of what is in the exercises table: a live summarize row is simply never a
     candidate. The degraded-grader rule (docs/05 section 4) still applies on
     top, for when summarize is deliberately enabled.
     REJECTED: retiring the live summarize rows and calling it fixed. That is
     what the previous state effectively relied on, and it fails the moment
     anyone publishes summarize content again. Data is not a control.
     REJECTED: deleting summarize from the codebase. It is built, tested and
     hardened (M5), and A-phase may want it back; the decision is to not SHIP it,
     not to not HAVE it.
     TESTS: a live summarize row plus a healthy grader is never sampled; it is
     excluded even when it is the ONLY live content (the degradation pad must not
     be a back door -- correct outcome is an empty, transient session per D-59);
     and a positive control proving the switch is what does the work, so a
     sampler broken for every type could not pass as a fix. Verified to fail
     against the pre-fix code (2 of 4 failed).
     INTERIM APPLIED IN PRODUCTION 2026-07-18, AND IT IS NOT THE FIX. The
     SUMMARIZE_ENABLED control is on master and master is UNSHIPPED, so
     production still evaluates ALL_CANDIDATE_TYPES on the healthy-grader path.
     Until v2 deploys, the only thing keeping summarize out of a production
     session is the absence of live summarize content -- which is exactly the
     non-control this entry exists to criticise. It is being relied on
     deliberately and temporarily, with that understood.
     WHAT WAS DONE: pg_dump of production first (custom format, validated with
     pg_restore -l: 17 table-data entries including exercises/users/attempts),
     then a single statement:
       UPDATE exercises SET status='retired' WHERE type='summarize' AND status='live';
     One row. Checked before running: zero in-flight daily_sessions referenced
     it and zero attempts existed against it, so no user session was disturbed.
     Production now has 0 live summarize rows.
     DO NOT READ THE RETIRED ROW AS THE PROTECTION. Publishing or un-retiring
     any summarize row before v2 ships re-opens the exposure immediately and
     silently. The real control is SUMMARIZE_ENABLED=false, and it takes effect
     only when the backend deploys. Until then this is a data state, not a
     guarantee, and it is one careless status flip away from being gone.

D-124 A repair that would not beat the current streak is never offered, and is
     refused if requested. Found by using the app: the dashboard read "Restore
     your 1-day streak" to a user whose current streak was already 1.
     WHY IT IS NOT COSMETIC: a reset is repairable AT MOST ONCE (D-116). Taking
     that offer would have spent the user's only repair of that reset to move
     their streak from 1 to 1. The affordance was not merely useless, it was
     actively harmful, and it was pointed at exactly the busy-professional
     audience A1 exists to protect.
     CAUSE: repair_available was defined as "a repairable reset exists"
     (restores_to is not None) and never compared the restore value against the
     streak the user already has.
     DECIDED: gate it in the API, not the UI. Two reasons. First, a client must
     not be ABLE to render a meaningless offer; putting the rule in the client
     means every future client (and the next screen that reads these fields)
     re-derives it or forgets. Second, and stronger: hiding an affordance is not
     preventing an action, so POST /v1/streak/repair ALSO refuses with the
     existing 409 not_repairable. A stale tab, a replay, or a hand-rolled client
     cannot spend the one-shot on a no-op. The UI needs no change at all, which
     is the tell that the API was the right layer.
     D-116(b)'s identity is preserved deliberately: repair_available is still
     exactly (repair_restores_to is not None), because restorable_value() itself
     now returns None when the restore would not gain anything. Keeping the two
     in one place is what stops them disagreeing; a test asserts it.
     TESTS: the reported case (restore 1 vs streak 1) advertises nothing; the
     route refuses it even when called directly; and a positive control (restore
     8 vs streak 1) is still offered, still succeeds, and is then correctly
     no longer offered because the one-shot is spent.

D-125 Every full-height screen owns its own scroll container, and that is now
     tested. AppLayout's <main> is overflow-hidden, so each route must provide
     `overflow-y-auto` itself. Profile.tsx always did. Dashboard.tsx did not, and
     once A1 added the welcome-back panel the page grew past the fold and
     "Upcoming reviews" and "Recent sessions" became UNREACHABLE, not merely
     below the fold. One utility class.
     WHY 517 TESTS MISSED IT, and this is the general lesson: Playwright
     locators resolve and even CLICK elements that are clipped out of view, and
     nothing in the suite ever asserted layout. A screen can be completely
     unusable while every selector-based assertion stays green. The assertion has
     to be about SCROLLABILITY (scrollHeight > clientHeight, computed overflow-y,
     and scrollTop actually moving), not about presence.
     TEST: a hermetic spec at a laptop-height viewport WITH the welcome-back
     panel rendered, since that panel is what tips the page over. Profile is kept
     as the control so a future layout change cannot silently break both.
     Verified to fail against the unfixed code (computed overflow-y was not
     auto/scroll and scrollTop stayed 0).
     ALSO FOUND, and worth knowing before debugging anything else locally: the
     dockerised vite dev server does NOT hot-reload host edits on Windows (the
     bind mount does not deliver file-watch events into the container). The fix
     was on disk and the served module was stale, which is exactly the
     "testing stale bytes" hazard the Playwright webServer block was added to
     prevent. Restart the frontend container after editing frontend source, or
     run vite on the host.

D-127 Audit of the runtime-safety/security tier for false verification claims.
     Prompted by two entries in this workflow that asserted verification which
     had not happened: D-115 claimed "verified in code" and was wrong in the
     exact inverse direction (D-123), and D-119 cited a spec as evidence that
     was itself flaky (D-122). Both were treated as ground truth for weeks.
     SCOPE: entries that both claim something was verified/checked/confirmed AND
     gate a safety property, invariant, cost control, or injection surface. That
     filter returns 33 entries; this pass covers the 10 runtime ones. The 12
     pipeline/content-integrity entries (D-45, D-46, D-51, D-52, D-77, D-80,
     D-81, D-86, D-89, D-90, D-91, D-101) are NOT covered and remain unaudited.
     RESULT: all 10 HOLD against current code. No entry was false in the D-115
     way, so nothing here is a live bug.
       D-103 HOLDS in full. ErrorBoundary has getDerivedStateFromError +
         componentDidCatch -> Sentry.captureException; the root boundary with
         FullPageErrorFallback is in main.tsx; the per-exercise boundary in
         Session.tsx is keyed by currentIndex with a "Skip this exercise"
         fallback wired to handleNext; and revealViews.tsx carries three
         early-return guards to <RevealUnavailable /> (spot_the_bug, trace,
         predict_the_fix). One imprecision, not an error: the guards are all in
         revealViews.tsx, not "revealViews.tsx / Reveal.tsx".
       D-66 SUPERSEDED, not stale or false. Its per-(user, exercise, date) lock
         key is no longer what the code does, because D-104 deliberately
         re-keyed it to per-(user, day). Current code matches D-104. Reading
         D-66 alone would mislead; it is correct as history.
       D-104 HOLDS. attempts/service.py locks on (user_id, today.isoformat()).
       D-88 HOLDS. conftest.py calls assert_disposable_test_database three
         times (module load, and again at the destructive fixture).
       D-92 HOLDS. BETA_GATE_ENABLED defaults false and gates exactly the two
         enforcement points (auth/router.py:132, auth/service.py:232).
       D-106 HOLDS. usePanel is used by both Dashboard and Profile.
       D-107 HOLDS. POST /v1/attempts is not in the rate-limit exempt list;
         _SAFE_REQUEST_ID sanitises X-Request-ID; resolve_client_ip honours
         trusted_proxy_count.
       D-111 HOLDS. No SessionGate remains anywhere in frontend/src.
       D-112 HOLDS, and was independently confirmed live this session: dumping
         production logged "dropped 1 query param(s) asyncpg cannot accept:
         channel_binding", which is precisely the behaviour it describes.
       D-113 HOLDS. backend/pyproject.toml asks for fastapi[standard].
     THE ONE FINDING WORTH CARRYING FORWARD, from D-103: its verification was
     genuine when written AND its evidence later decayed without anyone
     noticing. reveal-error-boundary.spec.ts was failing 11 runs in 15 because
     of D-122's unrelated session-build race, so for some period "verified by a
     passing Playwright test" was false while the entry still read as settled.
     It is now 15 of 15. A test-backed claim is only as durable as the test, and
     nothing in this repo alerts when a cited test starts failing intermittently.
     That, not any individual entry, is the systemic gap this audit found.
     NOT DONE: the pipeline/content tier. Worth a pass before the corpus grows
     again, since those entries gate content correctness rather than runtime
     behaviour and their evidence is generation-run output that cannot be
     re-executed cheaply.

D-128 CI has been RED ON EVERY PUSH SINCE 2026-07-06 and nothing surfaced it.
     This is the same failure mode as D-119's ignored spec, one layer up, and it
     is the mechanism behind D-127's finding that D-103's verification decayed
     unnoticed.
     EVIDENCE (GitHub Actions API, 2026-07-18): 11 consecutive failed runs. The
     three pushes of the A1/A2 merge work failed identically (be3cce4 master,
     5efa1bf a1, 75ef92c a2), as did every push back to a847510 on 07-06. ALL
     FOUR jobs fail in every run.
     WHAT ACTUALLY FAILS, per job:
       pytest  -- fails at "Initialize containers", so steps 5 through 9 are
         SKIPPED and `pytest backend/tests` HAS NEVER EXECUTED IN CI. The suite
         is configured to run on push and has not run once.
       schema  -- same, fails at "Initialize containers".
       ruff    -- `ruff check backend` fails on backend/main.py: an unsorted
         import block in a deploy shim carrying leftover debug scaffolding
         (`sys.stderr.write('--- LOADING MAIN.PY ---')` and a try/except that
         re-raised after printing a traceback). Reproduced locally and FIXED
         here: the shim is now the bare re-export it should always have been.
       dependency-audit -- `pip-audit --strict` run against the ENVIRONMENT can
         never pass, because `pip install -e backend` puts our own editable
         `codereader-backend` in it, pip-audit cannot resolve it on PyPI, and
         --strict turns "could not audit" into a failure. `--skip-editable` does
         not help either: --strict also fails on skips. So this job has been red
         since it was written. HANDOFF had already noticed the symptom ("CI
         dependency-audit job has never run against live advisory feeds")
         without ever finding the cause.
     THE ONE I COULD NOT DIAGNOSE: "Initialize containers". Step outcomes are
     readable anonymously through the API; LOGS are not. Diagnosing it needs an
     authenticated `gh run view --log-failed`, which is why the fix for the two
     container jobs is handed back rather than guessed at. Guessing is what
     D-119 punished.
     REJECTED: rewriting the working `services:` blocks on a hunch. The
     single-quoted `--health-cmd 'pg_isready ...'` form is a plausible suspect
     and it is ALSO the form GitHub documents, so changing it blind would be a
     coin flip dressed as a fix.
     CHANGE (config only, no dependency changed): pip-audit now audits the
     resolved set from `pip freeze --exclude-editable` rather than the
     environment, which keeps --strict meaningful while excluding our own
     unpublishable package.
     REAL ADVISORIES, NOW VISIBLE FOR THE FIRST TIME and NOT acted on, because
     both fixes are blocked by our own upper bounds and that is a dependency
     decision, not a CI fix: cryptography 45.0.7 has 6 advisories (PYSEC-2026-35,
     PYSEC-2026-36, PYSEC-2026-2141, GHSA-537c-gmf6-5ccf) fixed in 46.0.5 through
     48.0.1, while pyproject pins `cryptography>=43.0,<46.0`; pytest 8.4.2 has
     PYSEC-2026-1845 fixed in 9.0.3, while pyproject pins `pytest>=8.3,<9.0`.
     Both ceilings must be raised for the job to go green, and cryptography
     46/48 is a major bump on a security-relevant library.
     NEW: a `playwright` job. The e2e suite had NO CI job at all, which is the
     DIRECT cause of the D-103 decay: a cited Playwright spec started failing
     11 runs in 15 (D-122's session-build race) and nothing surfaced it, so the
     entry kept reading as "verified by a passing test" while the test was
     failing. Auditing (D-127) catches entries that were never true; only this
     catches entries that STOP being true. The job runs Postgres and Redis as
     services, migrates, seeds, starts uvicorn, and lets Playwright own its own
     vite (reuseExistingServer false, so it can never test stale bytes), with
     SUMMARIZE_ENABLED and EMAIL_SENDING_ENABLED both false so the suite can
     neither sample a summarize exercise nor send mail.
     PROCESS FAILURE OF MY OWN, recorded because it is the same shape: I ran
     `ruff check backend/app backend/tests` all session and reported "All checks
     passed", while CI runs `ruff check backend`. My narrower scope silently
     excluded the one file that was failing. The rule going forward is to run
     exactly what CI runs before reporting green, and to name the command.

D-126 RECORDED LATE, and the lateness is the first thing worth saying. The
     dev-link log in email/sender.py cites "D-126" three times and
     test_a2_email_capture.py cites it once, but no D-126 entry was ever
     written: docs/07 jumps D-125 -> D-127. A citation pointing at nothing is
     worse than no citation, because it reads as "this was decided and
     reviewed" to anyone who does not go looking. Found while building A3 on
     top of that exact mechanism. THE DECISION, as built: with
     EMAIL_SENDING_ENABLED false no mail exists, and the verification token is
     sha256-hashed at rest and deliberately never logged (D-120(4)), which
     left no way to walk the verify path locally at all. DisabledEmailSender
     therefore logs the actionable link. It is DOUBLE-GATED and the first gate
     is structural: the class is only ever constructed by get_email_sender()
     when the off-switch is false, so a sending deploy never reaches the code.
     The explicit re-check of the setting inside send() covers the one way
     that could be defeated, someone constructing DisabledEmailSender
     directly. OutboundEmail.dev_link carries the link as its own field rather
     than regex-scraping the body, and the real sender never reads it and
     never puts it in the provider payload. A3 extends this unchanged: the
     reminder and recap messages set dev_link to their unsubscribe URL, which
     is the one link in them worth walking locally.
     ALSO MISSING, not fixed here because it belongs to the viewer-mobile
     branch and not to A3: D-135 is cited in config.py's APP_ORIGIN comment
     and in a commit subject, and has no entry either, even though the commit
     that introduced it claims to "record D-129..D-136". Whoever lands
     viewer-mobile owes that entry.

D-137 A3 reminders and weekly recap. Send-once is the whole problem, and it is
     answered with a LEDGER plus a provider idempotency key, not with a
     timestamp column. Ten decisions, written before any code.

     (0) THE PREREQUISITE THIS DOES NOT SOLVE, first, because both HANDOFF and
     docs/10 say A3 is BLOCKED on it and building the code does not unblock
     it. Resend will only send from a VERIFIED DOMAIN (SPF, DKIM, MX, DMARC).
     EMAIL_FROM still names no-reply@codereader.dev, a placeholder nobody
     owns, and neither codereader-eight.vercel.app nor
     codereader.fastapicloud.dev can be used because you cannot add DNS
     records to a domain you do not control. So "paste RESEND_API_KEY and flip
     EMAIL_SENDING_ENABLED" is necessary and NOT sufficient: without a
     verified domain every send returns a provider error, which this job will
     dutifully record as `failed` and retry to its cap. Everything else in A3
     is built and tested; this one item is procurement plus DNS propagation,
     and it is a lead-time item. APP_ORIGIN must move at the same time, since
     both verification links (D-120) and unsubscribe links (below) are built
     from it, and that touches D-114's same-origin rewrite and the
     GITHUB_REDIRECT_URI rule in docs/09 section 3.

     (1) ONLY VERIFIED ADDRESSES, ENFORCED IN ONE QUERY RATHER THAN AT EACH
     CALL SITE. D-120 already guarantees users.email holds only a verified
     address, so A3 could have simply trusted it. It does not: both jobs draw
     candidates from a single `eligible_recipients()` builder whose predicate
     is `email IS NOT NULL AND email_verified_at IS NOT NULL AND deleted_at IS
     NULL`. WHY BOTHER, given D-120: because "the column is only ever written
     with verified values" is an invariant held by a different module, and the
     job is the wrong place to depend on someone else's discipline. Two jobs
     sharing one predicate also means a future third job cannot get it subtly
     wrong. pending_email is never selected by the jobs module at all.

     (2) SEND-ONCE IS A LEDGER, AND THIS IS THE LOAD-BEARING DECISION.
     New table `email_deliveries`, PRIMARY KEY (user_id, kind, period_key).
     REJECTED: a `last_reminder_sent_at` timestamp on users, which is the
     obvious cheap shape. It fails for the same reason D-116 rejected
     inferring a covered day from the freeze balance: it makes "have we
     already sent for this period" a COMPUTATION at read time rather than a
     RECORDED FACT, and that computation depends on the user's timezone, which
     can change underneath it. A ledger keyed by the period is immune, because
     the key IS the answer. Same argument, one layer up, as D-116's "a covered
     day is read from the streak_events ledger".
     THE PK IS THE CEILING. Two overlapping job runs both attempt the claim;
     exactly one INSERT wins and the loser gets zero rows back and skips. This
     is the same un-raceable-DB-backstop discipline as
     uq_streak_events_one_transition_per_day (H1/D-104), and it holds without
     an advisory lock because unlike a streak transition there is nothing to
     read-modify-write.

     (3) CLAIM BEFORE SEND, COMMITTED SEPARATELY, AND `claimed` IS TERMINAL.
     The claim row is INSERTed and COMMITTED before the provider call. The
     alternative, send-then-record, has a window in which a crash loses the
     record and the next tick sends again.
     THE ASYMMETRY THAT DECIDES IT: a duplicate reminder is a channel
     violation, and docs/10's A3 line is "optimise copy and timing, never
     frequency (protect the channel)". A missed reminder is a non-event; the
     user opens the app or does not. So every ambiguous outcome must resolve
     to DO NOT SEND AGAIN.
     Hence three states and their exact meanings. `sent`: the provider
     accepted, terminal. `failed`: we caught a definite EmailSendError and
     COMMITTED that fact in its own transaction, so we know a send did not
     succeed; retryable, bounded by EMAIL_SEND_MAX_ATTEMPTS. `claimed`: the
     ambiguous state, meaning the process died between claim and outcome, or a
     send is in flight right now. TERMINAL, deliberately. We cannot distinguish
     "died before the POST" from "died after Resend accepted it", and guessing
     wrong in the retry direction double-sends.
     CONSEQUENCE, accepted: a crash at exactly the wrong moment costs that user
     that day's reminder. That is the cheap side of the trade, and it is the
     side docs/10 asks for.

     (4) THE PROVIDER IDEMPOTENCY KEY IS THE SECOND LAYER, AND IT IS WHAT MAKES
     RETRYING A `failed` ROW SAFE AT ALL. Every send carries
     `Idempotency-Key: {kind}:{user_id}:{period_key}`, deterministic from the
     ledger key. Resend deduplicates on it for 24 hours.
     WHY IT IS NOT OPTIONAL: a timeout is a `failed` we can commit but NOT a
     failure we can interpret. httpx raising ReadTimeout does not tell us
     whether the request landed. Without a provider-side key, retrying any
     timeout is a coin flip on a duplicate, which would make (3)'s guarantee a
     lie for precisely the most common transient failure. With it, the retry is
     safe by construction.
     SO THE TWO LAYERS DIVIDE CLEANLY: the PK stops the JOB sending twice; the
     Idempotency-Key stops the PROVIDER delivering twice when the job
     legitimately retries. This is the same discipline as invariant 4 (POST
     /attempts idempotent per Idempotency-Key), applied outbound.
     Retries are bounded to the period AND to 24h, because outside Resend's
     idempotency window the second layer is gone and (3) takes over.

     (5) PERIOD KEYS ARE USER-LOCAL, DERIVED THE WAY core/timezones.py ALREADY
     DERIVES EVERYTHING. reminder period_key is the user-local calendar date
     from `local_date_for(user.timezone)`, ISO `YYYY-MM-DD`: the same function
     and the same notion of "day" the streak uses, so a user cannot have a
     streak day and a reminder day that disagree. recap period_key is the ISO
     year-week of that same local date, `%G-W%V`, e.g. `2026-W29`.
     DST IS A NON-EVENT FOR THE KEY: a 23- or 25-hour day is still exactly one
     calendar date, so the ledger key is unaffected in both directions.
     DST DOES MATTER FOR ELIGIBILITY, and is why the window is WIDE rather than
     an exact match. Eligibility is `current local time >= reminder_local_time`
     for the whole remainder of the local day, not "just passed". SPRING
     FORWARD with a reminder at 02:30 and 02:00 -> 03:00 skipped: an exact
     match never fires and the user silently loses that day; the wide window
     fires at 03:00, late rather than never. FALL BACK with a repeated hour:
     the first tick past 01:30 claims the row, the second 01:30 finds it and
     skips. One send. The wide window is only safe BECAUSE of (2); with a
     timestamp column it would re-send all evening.
     TIMEZONE CHANGE, and here streak_recon.py's precedent applies directly.
     That module protects the WESTWARD direction, where the boundary moves
     backward and would otherwise destroy something, and deliberately leaves
     eastward alone. Same asymmetry: moving WESTWARD lands on a local date
     whose key is already in the ledger, so no second send, protected for free
     by (2). Moving EASTWARD can produce a fresh local date and therefore a
     second reminder inside one absolute 24 hours. ACCEPTED, bounded at one
     extra, and it is the honest reading of "one per local day" -- the user
     really is in a new day. NOT reusing reconcile_streak_for_timezone_change:
     that repairs streak bookkeeping, and delivery has no equivalent thing to
     repair.

     (6) SUPPRESSION IS PERMANENT, KEYED ON THE USER, AND ORTHOGONAL TO
     reminder_local_time. New table `email_suppressions`, PK (user_id, kind),
     kind IN ('reminder','recap','all').
     KEYED ON user_id AND NOT ON THE ADDRESS. This is the entire reason "an
     unsubscribe survives a re-verify" is true BY CONSTRUCTION rather than by a
     check somebody has to remember to write. DELETE /me/email followed by a
     new address and a fresh verification never touches this table, so the
     suppression is still standing. Keyed on the address it would resurrect,
     which is the exact bug.
     PERMANENT: no expiry column, and nothing in the job path ever clears a
     row. The only way back on is an explicit authenticated opt-in on Profile,
     a deliberate act by the account owner, which is also the only defensible
     basis for re-consent.
     ORTHOGONAL TO reminder_local_time, stated because conflating them is the
     obvious shortcut and it silently breaks the unsubscribe.
     reminder_local_time is a SCHEDULE ("when"), suppression is a CONSENT
     ("whether"). Setting a time does not clear a suppression and clearing a
     suppression does not set a time; the job requires BOTH a non-NULL time and
     no suppression. Otherwise an unrelated settings change would undo an
     unsubscribe.
     'all' exists so a spam complaint can stop everything, which is what a
     complaint means; per-type is for a user choosing between them.

     (7) UNSUBSCRIBE IS A STATELESS HMAC, WHICH IS THE OPPOSITE OF D-120(4)'s
     STORED TOKEN, AND THE DIFFERENCE IS DELIBERATE. Token is
     `b64url(payload).b64url(hmac_sha256(key, payload))` over `user_id:kind`,
     domain-separated with a constant `unsub-v1` prefix so an unsubscribe token
     and a JWT can never be confused even though both derive from JWT_SECRET.
     Compared with hmac.compare_digest.
     NO EXPIRY, deliberately: an unsubscribe link in a two-year-old email must
     still work, which is both a deliverability expectation and the point of
     the mechanism.
     WHY NOT STORED AND SINGLE-USE LIKE THE VERIFICATION TOKEN: because that
     token GRANTS something (it promotes an address), so single-use bounds the
     damage of a leak. This one only REVOKES. The worst case for a leaked
     unsubscribe token is that someone stops mail the owner can switch back on
     in-app, and single-use would be actively harmful, since any mail client
     that prefetches links would burn it before the human clicked. It also
     means no row per sent email, no cleanup job, and the link survives a
     restore.
     RFC 8058 ONE-CLICK NEEDS BOTH HEADERS OR NEITHER: `List-Unsubscribe` with
     the https URL and a mailto fallback, plus `List-Unsubscribe-Post:
     List-Unsubscribe=One-Click`. The POST target takes the token from the
     QUERY STRING and ignores the body, because the body a mail provider sends
     is the fixed form field `List-Unsubscribe=One-Click`. It is unauthenticated
     and CSRF-exempt by nature: there is no session, and "an attacker makes you
     stop receiving marketing email you can re-enable in one click" is not a
     threat worth a token exchange.
     THE HUMAN LINK IN THE BODY POINTS AT THE SPA, NOT AT THE API. GET must not
     act: prefetchers and link scanners follow GETs. The SPA page reads the
     token and POSTs on a button press. Same one-click token, two entry points.

     (8) THE RECAP GOES OUT MONDAY 09:00 USER-LOCAL, AND REPORTS THE WEEK THAT
     JUST ENDED. RECAP_LOCAL_WEEKDAY=0, RECAP_LOCAL_HOUR=9.
     WHY MONDAY: the ISO week ends Sunday, so Monday is the first moment the
     week being reported is COMPLETE. A Sunday-evening send would silently omit
     Sunday, which is a recap that is wrong rather than early.
     WHY 09:00 AND WHY FIXED RATHER THAN AT reminder_local_time: a fixed hour
     keeps (6)'s orthogonality honest, and it keeps the recap from landing in
     the same minute as the daily reminder for users whose reminder is set to
     the morning. Two of our emails arriving together is the "protect the
     channel" failure in its most literal form.
     CONTENT IS DERIVED, NO NEW COUNTERS, per the brief. Sessions completed
     from daily_sessions (session_date in the week, completed_at NOT NULL);
     exercises and accuracy from attempts (session_date in the week, graded
     rows only as the denominator, matching accuracy's existing meaning);
     streak state from user_stats.
     "CONCEPTS IMPROVED" IS REPORTED AS "CONCEPTS PRACTISED CORRECTLY", and the
     rename is the honest part. user_concept_state.mastery is a CURRENT
     SNAPSHOT with no history, so a real week-over-week delta is not derivable
     from existing tables, and manufacturing one means storing a weekly mastery
     sample, which is a new counter. So the recap says what is true: which
     concepts were answered correctly this week, from attempts joined to
     exercises.concepts.
     AN EMPTY WEEK IS NOT SENT. Zero attempts in the week writes a terminal
     `skipped` ledger row and no mail. A report of nothing is not a report, and
     "here is your week: nothing" is guilt copy no matter how it is worded,
     which docs/10 rules out. The reminder is the nudge; the recap is the
     report.

     (9) COPY AND VOICE: NO GUILT, NO STREAK-LOSS THREAT, per docs/10's two
     hard rules and docs/08's voice. The reminder does not mention what will be
     lost, does not count down, and does not use the streak as leverage; it
     says what is waiting. Concretely BANNED in these two templates: "don't
     lose", "you'll lose", "your streak ends", "last chance", "still time",
     scarcity framing, and any exclamation mark. A1 already replaced the reset
     path with a welcome-back state precisely so nothing in the product
     threatens a streak; an email that did so would reintroduce the thing A1
     removed, out of the user's sight, in their inbox.

     (10) BATCHING IS SEQUENTIAL AND PACED, NOT CONCURRENT.
     EMAIL_JOB_BATCH_SIZE=200 candidates per tick, EMAIL_MAX_SENDS_PER_TICK=100
     actually sent, paced at EMAIL_SENDS_PER_SECOND=2 (Resend's documented
     default rate limit).
     WHY NOT A CONCURRENT FAN-OUT: 200 simultaneous POSTs earns an immediate
     429 from any provider, and then we own a retry-storm problem strictly
     worse than being slow inside a background job that nobody is waiting on.
     THE CAP DEFERS RATHER THAN DROPS, and that only works because (5)'s window
     is wide: a user not reached this tick is still eligible next tick, because
     eligibility runs to the end of their local day.
     VOLUME AT 1,000 FULLY-SUBSCRIBED USERS: 1,000 reminders/day plus 1,000
     recaps on Mondays, so a peak day of ~2,000 sends. At 2/s that is ~1,000
     seconds of job time, drawn down 100 per tick against a 300s reminder tick.
     Worst case, every one of the 1,000 sharing a single local reminder minute,
     the last user is reached roughly 50 minutes late; realistic timezone and
     time-of-day spread makes it far less, and 50 minutes late on a daily
     reminder is not a defect.
     THE REAL CEILING AT THAT SCALE IS THE RESEND PLAN, NOT THIS CODE: the free
     tier is 100/day and 3,000/month, which 1,000 subscribed users exceed on
     day one. That is a procurement decision to make alongside (0), and the job
     will surface it as `failed` rows with a provider error rather than as
     silence.

     FAILURE ISOLATION, and it is per-user, not just per-job. JobScheduler
     already isolates one job from another. A3 adds the inner ring: each
     recipient's claim-send-record runs in its own transaction inside its own
     try/except, so one bad address cannot end the sweep for the other 199.
     A definite EmailSendError records `failed` and continues; any other
     exception logs and leaves the row `claimed` per (3), and continues.
     last_error stores the exception TYPE only, never the message and never the
     body, matching D-120's logging discipline (an httpx error can carry the
     request body, and that body is somebody's mail).

     BOUNCE AND COMPLAINT SUPPRESSION IS DEFERRED, EXPLICITLY. The webhook is
     not built. It would be a Resend-signed endpoint verifying the signing
     secret, handling `email.bounced` (hard bounces only) and
     `email.complained`, writing `email_suppressions(kind='all',
     reason='bounce'|'complaint', source='webhook')`. It is deferred because it
     needs a public HTTPS endpoint and a signing secret that do not exist until
     (0) is resolved, and an untestable endpoint shipped now is a liability
     rather than a feature. The table carries `reason` and `source` from the
     start SO THAT adding it later is an endpoint and not a migration.

     OFF-SWITCH: unchanged from A2 and structural for the same reason. The jobs
     resolve their sender through get_email_sender(), so with
     EMAIL_SENDING_ENABLED false they hold a DisabledEmailSender that never
     constructs a request, never imports a transport and never resolves a
     hostname. The ledger still fills in, which is what makes the whole flow
     walkable locally with nothing leaving the process.
