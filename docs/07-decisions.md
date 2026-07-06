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
