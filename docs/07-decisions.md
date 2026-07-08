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
