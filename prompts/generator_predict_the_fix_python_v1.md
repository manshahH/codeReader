# prompt_template_id: ptf_py_v1
# Type: predict_the_fix | Language: Python {{python_version}} | Temp: 0.8
# System + user prompt below. Everything between BEGIN/END markers is sent to the model.
# predict_the_fix is DERIVED from an already-sandbox-verified spot_the_bug
# candidate (D-80): its (buggy_code, fixed_code, test_code) triple is proven,
# by execution, to fail on buggy and pass on fixed. This template asks ONLY for
# 3 WRONG fix variants; the correct choice is the verified fixed_code, never a
# model claim. Every wrong variant is then EXECUTED against the same test in
# the sandbox and MUST STILL FAIL (raise AssertionError) -- a variant that
# passes is not wrong and rejects the whole candidate. No LLM judgment enters
# the answer key; the ground truth is execution, same as every other type.

================================ BEGIN SYSTEM ================================
You are a senior Python engineer writing code-comprehension exercises for working
developers. You are given a real bug, its correct fix, and a test that passes
only on the correct fix. Your job is to write plausible-but-WRONG fixes: changes
a competent engineer might reach for that do NOT actually make the test pass. You
output a single JSON object and nothing else: no markdown fences, no commentary.
================================= END SYSTEM =================================

================================ BEGIN USER ==================================
Here is a verified bug and its correct fix.

## Concept (the bug's mechanism)
{{concept}}

## Domain flavor
{{domain}}

## buggy_code (what the user will see; it fails the test below)
{{buggy_code}}

## fixed_code (the ONE correct fix; the test passes on this and only this)
{{fixed_code}}

## test_code (fails on buggy_code, passes on fixed_code; both proven by execution)
{{test_code}}

## Your task
Write exactly 3 WRONG fix variants. Each is a full, standalone replacement for
buggy_code (the entire code, the same way fixed_code is a full replacement) that
LOOKS like a reasonable attempt to fix the bug but does NOT actually fix it, so
the given test_code STILL FAILS against it.

## Hard constraints
1. Runs on Python {{python_version}}, stdlib only, deterministic. Same forbidden
   list as every exercise: random, time/now, file/network I/O, threading,
   asyncio, subprocess, input(), env reads, uuid, id(), iterating/printing sets,
   dict-order-dependent output.
2. Each wrong variant MUST run without raising on the test's happy path and MUST
   STILL FAIL the given test_code -- it fails the ASSERTION (produces the wrong
   value / wrong state that the test catches), it does not crash. If test_code
   converts a specific exception to AssertionError, triggering that path is a
   legitimate failure too; a bare uncaught non-AssertionError exception is NOT
   (it would read as broken code, not a plausible fix).
3. Each wrong variant must be a plausible fix: the kind of change a real
   engineer might make that addresses a symptom, or the wrong boundary, or a
   related-but-different concern -- not obvious nonsense.
4. Each wrong variant must be DIFFERENT from buggy_code, from fixed_code, and
   from the other wrong variants. Do NOT submit buggy_code unchanged as a
   "fix" and do NOT submit anything equivalent to fixed_code.
5. No comments, docstrings, or names that hint at correctness/wrongness (no
   `wrong_fix`, `broken`, `# does not work`). Write it as if it were a real
   proposed fix.

Worked example (bug: off-by-one on a threshold, `>` where it should be `>=`;
fixed_code changes `>` to `>=`; test asserts tier_discount(100) == 0.10):
  A plausible WRONG fix: change the RETURN VALUE instead of the comparison --
  `if order_total > 100: return 0.10` left as-is but the else branch returns
  0.05 instead of 0.0. It looks like tuning the discount, but tier_discount(100)
  still returns the else value, not 0.10, so the test still fails. note: "adjusts
  the wrong branch's return value; the boundary at exactly 100 is still missed."

## Output JSON (exactly this shape)
{
  "wrong_fixes": [
    {"code": "<full standalone code, a plausible fix that STILL FAILS the test>", "note": "<one sentence: why it looks right but does not make the test pass>"},
    {"code": "<...>", "note": "<...>"},
    {"code": "<...>", "note": "<...>"}
  ]
}

If you cannot write 3 genuinely-plausible wrong fixes that all still fail the
test, output {"abort": true, "reason": "<why>"}. Aborting beats shipping a
distractor that accidentally passes (it would be a second correct answer).
================================= END USER ===================================

# ---------------------------------------------------------------------------
# Pipeline notes (NOT sent to the model)
#
# * The correct choice is fixed_code, execution-verified upstream (the STB
#   sandbox gate proved test fails on buggy, passes on fixed). It is NEVER a
#   model claim.
# * Sandbox validation for this template (pipeline/sandbox_gate.validate_
#   predict_the_fix):
#     1. exec(fixed_code + test_code)      -> must PASS (correct choice holds)
#     2. exec(buggy_code + test_code)      -> must FAIL (AssertionError); its
#        output is captured for the payload's "failing test output"
#     3. for EACH wrong variant: exec(variant + test_code) -> must STILL FAIL
#        with AssertionError. A variant that PASSES is not wrong -> reject the
#        whole candidate (the new invariant). Run twice; nondeterminism rejects.
#     4. every variant must be textually distinct from buggy_code, fixed_code,
#        and every other variant.
# * Grading is deterministic (choice_id), same as trace -- zero per-answer LLM
#   cost. The wrong-fix `note` fields become the reveal's why-wrong lines.
# * Static gate runs on every variant (forbidden imports/calls, hint words,
#   max line budget), same as any shipped code.
# ---------------------------------------------------------------------------
