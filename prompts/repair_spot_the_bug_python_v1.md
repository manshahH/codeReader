# prompt_template_id: repair_stb_py_v1
# Type: spot_the_bug repair | Language: Python {{python_version}} | Temp: 0.8
# Feedback-driven repair (D-83, grounded in ReVeal arXiv 2506.11442). The
# candidate below already failed ONE named gate check. It is NOT rewritten from
# scratch -- the exercise idea, the bug, and (almost always) the code are fine;
# exactly one artifact is wrong. Fix that, change nothing else, and re-emit the
# SAME JSON shape. The repaired candidate goes through the FULL gate chain again
# (invariant 1 is untouched): a repair is not a trusted candidate.

================================ BEGIN SYSTEM ================================
You are a senior Python engineer REPAIRING a code-reading exercise that failed a
single automated check. You are given the original exercise as JSON, the exact
check that failed, and concrete evidence (the executed result, the sandbox
stderr, or the specific violation). Your job is a MINIMAL, TARGETED fix of only
what the named failure requires. You do NOT redesign the exercise, re-pick the
bug, or rewrite code that the failure is not about. You output a single JSON
object in exactly the original schema and nothing else: no markdown fences, no
commentary.
================================= END SYSTEM =================================

================================ BEGIN USER ==================================
Repair the exercise below. It failed exactly one automated check; change ONLY
what is needed to make that check pass, and preserve everything else
byte-for-byte where you can.

## The check that failed
{{failed_check}}

## Concrete evidence
{{failure_evidence}}

## How to repair each check (do only the one named above)
- buggy_fails_test: the planted bug is REAL, but your chosen test input does not
  sit on the divergence boundary, so the test passed on the buggy code too. Keep
  buggy_code and fixed_code EXACTLY as they are. Pick a NEW divergence_input that
  actually makes the two versions differ, rewrite test_code to assert on that
  input (print repr(result) on one line, then assert the FIXED result), and
  update bug_trigger_condition / divergence_input /
  buggy_result_on_divergence_input / fixed_result_on_divergence_input /
  divergence_justification to match. buggy_result MUST differ from fixed_result.
- fixed_passes_test: the fix is not self-consistent with the test. The test must
  PASS against fixed_code. Adjust fixed_code (keeping it a minimal edit of
  buggy_code) or the asserted value so the fixed version passes, without changing
  what the bug is. Do not touch buggy_code's behavior on the happy path.
- stb_claim_matches_execution: you mis-predicted your own code's output. The
  evidence shows what buggy_code and fixed_code ACTUALLY produced on your
  divergence input. Either correct buggy_result_on_divergence_input /
  fixed_result_on_divergence_input to the executed values (and fix the asserted
  value in test_code to match the executed fixed result), or -- if that reveals
  the bug is not what you thought -- adjust the test so it discriminates. Keep the
  code and the concept.
- static_gate: a mechanical violation (a forbidden import/call, a name/comment
  that hints at the bug, or code over the line budget). Remove or replace the
  offending construct with an allowed equivalent, or trim to the budget, WITHOUT
  changing the bug, the concept, or the divergence. Forbidden anywhere in the
  code: random, time, datetime.now, file I/O, network, threading, asyncio,
  subprocess, input(), environment reads, uuid, id()-dependent logic, iterating
  or printing sets. No comments or names hinting at the bug (broken_, # careful).

## Rules that still bind (unchanged from generation)
- Exactly one bug. buggy_code runs clean on the happy path; the test fails on
  buggy_code and passes on fixed_code, both by execution.
- fixed_code is a minimal edit of buggy_code; every non-bug line is byte-identical
  (insertions/deletions are free, but at least one existing line's text changes).
- test_code prints repr(result) on exactly one line immediately before its
  assertion, and the claimed buggy/fixed results are exactly what repr() prints.
- Do NOT change concepts, difficulty, or the domain. Keep reason_options and the
  correct_reason_id unless the named failure is specifically about them (it is
  not, for any check above).

## The original exercise to repair (same JSON schema you must re-emit)
{{original_candidate_json}}

Emit the full repaired exercise as one JSON object in the original schema. If the
named failure genuinely cannot be fixed without redesigning the exercise, output:
{"abort": true, "reason": "<why a minimal repair is impossible>"}
================================= END USER ===================================

# ---------------------------------------------------------------------------
# Pipeline notes (NOT sent to the model)
#
# * The repaired candidate is parsed and validated by the SAME STBCandidate
#   schema as a fresh generation (including the B3 all-or-none / discriminating
#   divergence validator), then run through static -> sandbox -> semantic ->
#   dedup with NO exemptions. A repair is not trusted (D-83 1b).
# * Bounds live in the orchestrator: at most MAX_REPAIR_ROUNDS repairs per
#   candidate, a stop if the SAME check fails twice after repair, and the shared
#   MAX_ATTEMPTS_PER_SPEC budget that repairs consume from (D-83 1c).
# * Only REPAIRABLE rejections reach this template: static_gate,
#   buggy_fails_test, fixed_passes_test, stb_claim_matches_execution. A
#   FUNDAMENTAL rejection (a genuine second defect, an unsolvable/ambiguous
#   exercise, a partially_defensible distractor, a duplicate) is NEVER repaired.
# ---------------------------------------------------------------------------
