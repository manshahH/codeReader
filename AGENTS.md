# CLAUDE.md

Daily code-reading practice app for working developers ("Duolingo for reading,
reviewing, and debugging code"). You are building the MVP defined in docs/03
against the roadmap in docs/06.

## Read order
1. This file
2. docs/06-implementation-plan.md (roadmap, repo layout, stack, milestones)
3. The reference doc named by the milestone you are working on
4. docs/07-decisions.md before proposing any design change

## Doc map
- docs/00-product.md          what we are building and why
- docs/01-content-spec.md     exercise schema + generation/validation pipeline
- docs/02-architecture-full.md  end-state architecture (context, not MVP scope)
- docs/03-mvp-scope.md        what is in/out NOW; security + perf floor
- docs/04-database.md         schema rationale; DDL in db/schema.sql
- docs/05-api-contract.md     the API, exactly; section 8 = CI-enforced invariants
- docs/06-implementation-plan.md  milestones M0-M8 with acceptance criteria
- docs/07-decisions.md        decision log; divergences are recorded here FIRST
- docs/08-frontend-design.md  binding design direction; M6 cannot start without it
- docs/09-fastapi-cloud-deployment.md deployment runbook for backend and OAuth
- prompts/                    generator + gate templates; dryrun_stb_validation.py
                              is the executable reference for the sandbox gate

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
