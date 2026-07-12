# prompt_template_id: repair_trace_py_v1
# Type: trace repair | Language: Python {{python_version}} | Temp: 0.8
# Feedback-driven repair (D-83, grounded in ReVeal arXiv 2506.11442). The trace
# candidate below failed ONE named check. Fix only what the failure requires and
# re-emit the SAME JSON shape; the repaired candidate goes through the full gate
# chain again.

================================ BEGIN SYSTEM ================================
You are a senior Python engineer REPAIRING a "trace the output" exercise that
failed a single automated check. You are given the original exercise as JSON, the
check that failed, and concrete evidence (the code's REAL captured stdout vs the
output you claimed). Your job is a MINIMAL, TARGETED fix. You do NOT redesign the
exercise or rewrite code the failure is not about. You output a single JSON object
in exactly the original schema and nothing else: no markdown fences, no commentary.
================================= END SYSTEM =================================

================================ BEGIN USER ==================================
Repair the exercise below. It failed exactly one automated check; change ONLY
what is needed to make that check pass, and preserve everything else where you
can.

## The check that failed
{{failed_check}}

## Concrete evidence
{{failure_evidence}}

## How to repair each check (do only the one named above)
- captured_output_matches_claim: you mis-traced your own code. The evidence shows
  the code's REAL captured stdout. Do NOT change the code. Re-trace it carefully
  and make expected_stdout equal the REAL captured output; then set the CORRECT
  choice's text to that real output, and re-derive every distractor by applying
  its named misconception to the (now correct) trace so each distractor still
  differs from the correct output and from the others. Update the
  draft_explanation summary/trace_table/why_wrong to match the real execution.
- static_gate: a mechanical violation (a forbidden call, over the line budget, or
  a print pattern the gate rejects). Remove or replace the offending construct
  with an allowed equivalent, or trim to the budget, WITHOUT changing what the
  code prints. Forbidden: random, time/now, I/O, network, threading, asyncio,
  subprocess, input(), env reads, uuid, id(), iterating or printing sets.

## Rules that still bind (unchanged from generation)
- Deterministic output, 1-6 lines. Exactly one execution path.
- Exactly 4 choices: 1 correct plus 3 distractors, each the exact output under one
  named misconception; every choice distinct.
- why_wrong must cover exactly the 3 distractor ids.
- Do NOT change concepts, difficulty, or the domain.

## The original exercise to repair (same JSON schema you must re-emit)
{{original_candidate_json}}

Emit the full repaired exercise as one JSON object in the original schema. If the
named failure genuinely cannot be fixed without redesigning the exercise, output:
{"abort": true, "reason": "<why a minimal repair is impossible>"}
================================= END USER ===================================

# ---------------------------------------------------------------------------
# Pipeline notes (NOT sent to the model)
#
# * Re-validated by the SAME TraceCandidate schema (including the why_wrong
#   coverage validator), then re-run through the full gate chain with no
#   exemptions. Only REPAIRABLE trace rejections reach here:
#   captured_output_matches_claim and static_gate. Everything else (a solver
#   reject, a duplicate) is FUNDAMENTAL and never repaired (D-83).
# ---------------------------------------------------------------------------
