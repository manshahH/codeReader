# CLAUDE.md

Daily code-reading practice app for working developers ("Duolingo for reading,
reviewing, and debugging code"). Product name is **Reedkode** (public-facing
only, D-139); the repo, database and internal identifiers stay `codereader`
deliberately.

**PRODUCTION AND `master` ARE FAR APART. Check which one you mean.** Production
runs the MVP only. `master` additionally carries A1, A2, A3 and the mobile
viewer rebuild, none of it deployed. HANDOFF.md leads with the current split;
read it before assuming a feature is live.

## Read order
1. This file
2. HANDOFF.md (what is built, what is live, known issues, current content state)
3. docs/10-roadmap-retention.md (what we build next, phased) for feature work
4. The reference doc for the subsystem you touch (01 content, 04 db + db/schema.sql,
   05 api, 08/08b frontend, 09 deploy); docs/06 for the original MVP milestones
5. docs/07-decisions.md before proposing any design change (D-1..D-141)

## Doc map
- docs/00-product.md          what we are building and why
- docs/01-content-spec.md     exercise schema + generation/validation pipeline
- docs/02-architecture-full.md  end-state architecture (context, not MVP scope)
- docs/03-mvp-scope.md        what is in/out NOW; security + perf floor
- docs/04-database.md         schema rationale; DDL in db/schema.sql
- docs/05-api-contract.md     the API, exactly; section 9 = CI-enforced invariants
- docs/06-implementation-plan.md  milestones M0-M8 with acceptance criteria
- docs/07-decisions.md        decision log; divergences are recorded here FIRST
- docs/08-frontend-design.md  binding design direction; M6 cannot start without it
- docs/08b-frontend-tokens-APPROVED.md  the approved token set (D-98 made it dark-only)
- docs/09-fastapi-cloud-deployment.md  deploy runbook (FastAPI Cloud/Vercel/Neon)
- docs/10-roadmap-retention.md  what we build next: retention/gamification, phased
- docs/11-phone-surface-question.md  open question, superseded in part by D-129..D-136
- docs/ops-runbook.md          alert catalog, incident procedures
- docs/ops-incident-report-july-2026.md  the production incidents behind D-121/D-122
- HANDOFF.md                   current state: what is merged, what is deployed,
                               known issues, outstanding launch mechanics
- prompts/                    generator + gate templates; dryrun_stb_validation.py
                              is the executable reference for the sandbox gate

NOTE: docs/03 and docs/06 describe the ORIGINAL MVP plan and are partly historical
(see D-115: summarize is off, predict_the_fix shipped). HANDOFF.md is the truth for
current state.

## Non-negotiable invariants (test these, never weaken them)
1. No LLM claim is ever ground truth. Exercise answers come from sandbox
   execution (twin-snippet rule, captured stdout, double-run determinism).
2. grading and explanation JSONB never serialize to a client before a graded
   attempt exists. Response schemas are allowlists. A CI test enforces this.
3. Exercises are immutable per (id, version). Fixes bump version.
4. POST /attempts is idempotent per Idempotency-Key; replays byte-identical.
5. Every streak transition writes a streak_events row.
6. User free text is hostile input to the grader LLM: delimited data channel,
   strict JSON out, no tools.
7. Sandbox code is hostile: --network=none, resource-limited, credential-free
   host, never on the API machine.

## Conventions
- Stack and layout are pinned in docs/06; do not substitute libraries.
- db/schema.sql is the canonical shape; Alembic owns evolution after M1.
- Module law: routers -> services -> models; cross-domain via services only;
  pipeline touches backend only through the publish layer.
- Every gate/invariant gets at least one negative test proving it rejects bad
  input.
- Secrets only via config.py/env; keep .env.example current.
- If a doc and reality conflict, stop, add a D-entry to docs/07, then proceed.
- Frontend work loads the skills in skills/ (anti-slop-frontend,
  ui-ux-promax) before writing UI code; docs/08 workflow is mandatory.
- No em-dashes in any user-facing prose or docs.
