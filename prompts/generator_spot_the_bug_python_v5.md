# prompt_template_id: stb_py_v5
# Type: spot_the_bug | Language: Python {{python_version}} | Temp: 0.8
# System + user prompt below. Everything between BEGIN/END markers is sent to the model.
# v5 (D-86): prompt-cache optimization. The instructional content is byte-identical
# to v4 (D-82) EXCEPT that the varying `## Specification` block is relocated from
# the top of the user message to the very END, and the three inline references to
# the per-spec domain/concept in the body are genericized (they now point at the
# Specification below). The effect: the persona, difficulty scale, the disciplined
# order, the three worked examples, every constraint, and the output schema form
# one large, spec-INDEPENDENT prefix that OpenAI's prompt cache serves on every
# call, so only the ~one-paragraph spec is billed fresh. {{python_version}} is a
# pinned constant (always 3.12), so it stays inline without breaking the prefix.
# v4's decomposition, the free B3 schema check, and the B4 execution claim-check
# are all unchanged -- this is a caching change, not a generation-logic change.
#
#   B1 write the CORRECT code first, then plant exactly one bug -> buggy_code
#   B2 DERIVE the divergence: trigger condition, a concrete input, and the two
#      DIFFERENT results, as required fields
#   B3 free static check (schemas.py): buggy_result == fixed_result on the chosen
#      input => the model admitted its test cannot discriminate => rejected at
#      schema validation, before the sandbox is ever invoked (zero cost)
#   B4 the test prints repr(result) before asserting, so the sandbox captures the
#      ACTUAL buggy/fixed results and claim-checks them against the model's
#      prediction (D-11 for STB, in sandbox_gate.validate_spot_the_bug)

================================ BEGIN SYSTEM ================================
You are a senior Python engineer writing code-comprehension exercises for working
developers. Your exercises are realistic production code, not puzzles. You reason
in the disciplined order this prompt lays out -- correct code first, then one
planted bug, then the exact input where they diverge, then a test that pins that
input -- because a test that is not grounded in how the two versions diverge is
worthless. You output a single JSON object and nothing else: no markdown fences,
no commentary.
================================= END SYSTEM =================================

================================ BEGIN USER ==================================
Create one "spot the bug" exercise. Read all of the instructions, worked
examples, and constraints below FIRST; your specific assignment (concept,
difficulty, domain, line budget, has_bug) is in the Specification at the very
end.

## Difficulty scale (operational, not vibes)
- 1-2: bug visible in a single line once you look at it; common junior mistake
- 3-4: bug requires reading 2-3 functions together or tracking one variable's lifecycle
- 5-6: bug is a correct-looking pattern that fails on a specific input class or call
  sequence; requires mentally executing the code
- 7-8: bug is an interaction between two components that are each individually correct
- 9-10: bug survives a plausible test suite; only a precise edge case exposes it

## The order you MUST work in (do not skip a step)
This is the whole point of the exercise being reliable. Do it in this order:

STEP 1 -- Write the CORRECT implementation first. Realistic production code (in
the domain named in the Specification below) that does the right thing on every
input. This becomes fixed_code.

STEP 2 -- Plant EXACTLY ONE bug into a copy of the correct code, using the target
concept as the mechanism. The buggy version must still run without raising on the
happy path. This becomes buggy_code. (Writing buggy-first and back-filling a fix
is what produces fixes that are not self-consistent -- do not do it.)

STEP 3 -- DERIVE the divergence. A real bug produces the SAME output as the
correct code on MOST inputs; it misbehaves only on a specific input class. Find
that class and fill in, as required fields:
  - bug_trigger_condition: under exactly what input condition do buggy and fixed
    behave DIFFERENTLY? (e.g. "when the threshold is hit exactly", "when the list
    is empty", "when the same key appears twice", "on the SECOND call, because
    state leaked from the first")
  - divergence_input: a concrete input satisfying that condition.
  - buggy_result_on_divergence_input: what buggy_code returns for it, written as
    EXACTLY what Python's repr() prints (e.g. 0.0, None, ['a', 'b'], 'B2').
  - fixed_result_on_divergence_input: what fixed_code returns for it, same repr()
    form. THIS MUST DIFFER from buggy_result_on_divergence_input -- if the two are
    equal your test cannot discriminate and the candidate is rejected for free,
    before it ever runs.
  - divergence_justification: one sentence on why the two differ on this input.

STEP 4 -- Write the test that pins divergence_input. It computes the result on
divergence_input, PRINTS repr(result), then asserts the FIXED result:
    result = <call on divergence_input>
    print(repr(result))
    assert result == <fixed_result>, "<one-sentence reason>"
Because it prints repr(result), the sandbox captures the ACTUAL buggy and fixed
results and checks them against buggy_result_on_divergence_input /
fixed_result_on_divergence_input. If your prediction is wrong, the candidate is
rejected -- so run the code in your head against BOTH versions before finalizing.

STEP 5 -- Re-read buggy_code line by line for an accidental SECOND defect
(unintended off-by-one, an edge case in YOUR scaffolding). Scaffolding must be
boring and correct. Exactly one bug, or the candidate is rejected.

If has_bug is false: there is no bug and no divergence. STEP 2-4 do not apply;
fixed_code is byte-identical to buggy_code, bug_lines is [], the five divergence
fields are OMITTED entirely, and the test simply passes against the (correct)
code on a tricky-looking path.

## Worked examples (three structurally different divergence patterns)

### A. Boundary value (agree away from the boundary, differ AT it)
fixed_code (correct: "at least 100" is `>=`):
  1  def tier_discount(order_total):
  2      if order_total >= 100:
  3          return 0.10
  4      return 0.0
buggy_code (planted: `>` instead of `>=`):
  1  def tier_discount(order_total):
  2      if order_total > 100:
  3          return 0.10
  4      return 0.0
bug_trigger_condition: "order_total is exactly the threshold, 100"
divergence_input: "order_total = 100"
buggy_result_on_divergence_input: "0.0"
fixed_result_on_divergence_input: "0.1"
divergence_justification: "at exactly 100, > is False so buggy returns 0.0, while >= is True so fixed returns 0.1"
test_code:
  result = tier_discount(100)
  print(repr(result))
  assert result == 0.1, "spend of exactly 100 should earn the discount"
(At 150 both return 0.1; at 50 both return 0.0 -- off the boundary, a test using
only those would pass on buggy code too. bug_lines: [2].)

### B. Empty / degenerate collection (agree on non-empty input, differ on empty)
fixed_code (correct: an empty sample set has no peak):
  1  def peak(samples):
  2      if not samples:
  3          return None
  4      return max(samples)
buggy_code (planted: max(..., default=0) masks the empty case):
  1  def peak(samples):
  2      return max(samples, default=0)
bug_trigger_condition: "samples is empty"
divergence_input: "samples = []"
buggy_result_on_divergence_input: "0"
fixed_result_on_divergence_input: "None"
divergence_justification: "on [], buggy returns the default 0 while fixed returns None"
test_code:
  result = peak([])
  print(repr(result))
  assert result is None, "an empty sample set has no peak"
(On [3, 1, 2] both return 3. bug_lines: buggy_code's own line whose text the fix
replaces.)

### C. State leakage across calls (agree on the FIRST call, differ on the SECOND)
fixed_code (correct: fresh list per call):
  1  def add_tag(tag, tags=None):
  2      if tags is None:
  3          tags = []
  4      tags.append(tag)
  5      return tags
buggy_code (planted: mutable default shared across calls):
  1  def add_tag(tag, tags=[]):
  2      tags.append(tag)
  3      return tags
bug_trigger_condition: "the SECOND call that omits tags, because the default list persists"
divergence_input: "add_tag('a'); result = add_tag('b')"
buggy_result_on_divergence_input: "['a', 'b']"
fixed_result_on_divergence_input: "['b']"
divergence_justification: "the shared default keeps 'a' from the first call, so the second call sees ['a', 'b']"
test_code:
  add_tag('a')
  result = add_tag('b')
  print(repr(result))
  assert result == ['b'], "the second call must not see the first call's tags"
(A single-call test can never catch this -- the first call returns ['a'] on both.
bug_lines: [1].)

## Hard constraints on the code
1. Runs on Python {{python_version}}, stdlib only, no third-party imports.
2. Deterministic. FORBIDDEN anywhere in the code: random, time, datetime.now,
   os/sys interaction beyond argv-free execution, file I/O, network, threading,
   asyncio, subprocess, input(), environment reads, uuid, id()-dependent logic,
   iterating or printing sets, relying on dict ordering other than insertion order.
3. The buggy code MUST run without raising on the happy path. The bug is semantic:
   wrong value, wrong state, wrong behavior on an input class. Never a SyntaxError,
   NameError, or missing import. Exception-raising bugs are allowed only if the
   exception occurs on a non-obvious input, not on every call (and see constraint 13).
4. EXACTLY ONE bug if has_bug is true (STEP 5). Scaffolding must be boring and correct.
5. If has_bug is false: the code is correct, and it must LOOK suspicious enough
   that a careless reviewer would flag something. Use patterns that are commonly
   believed buggy but are correct in this context.
6. No comments, docstrings, or names that hint at the bug or its absence. Names
   like `broken_total` or comments like `# careful here` are automatic rejects.
   Write the comments a normal engineer would write, which is: few.
7. Realistic code in the target domain: real-looking entity names, plausible
   logic. No foo/bar, no lottery-ticket toy examples.
8. fixed_code must be a minimal, natural edit of buggy_code: change only what the
   bug requires. Every line NOT listed in bug_lines MUST be byte-identical between
   buggy_code and fixed_code, but the fix is free to INSERT new lines (a new
   import, a guard clause, wrapping in a `with`/`try` block) or DELETE lines -- the
   sandbox diffs buggy_code against fixed_code and only charges bug_lines with
   lines the fix actually REPLACES or DELETES; a purely INSERTED line shifts
   nothing and costs nothing. Do NOT plant dead scaffolding just so the fix avoids
   adding a line. The one requirement: at least one existing buggy_code line must
   have its own text replaced by the fix -- a 100%-new-lines fix gives bug_lines
   == [] (indistinguishable from has_bug=false) and is rejected.
9. bug_lines must be COMPUTED from a real diff, not estimated and not a naive
   position-by-position comparison. After writing both, align them the way a text
   diff would (matching unchanged lines by content, not index) and record the
   buggy_code line numbers (1-indexed) the alignment marks replaced or deleted.
   Lines the fix only inserts are never in bug_lines; a line that merely SHIFTED
   because an earlier line was inserted/deleted is not in bug_lines either. If
   has_bug is false, bug_lines is [] and fixed_code is byte-for-byte identical.

## Hard constraints on the test
10. test_code is a standalone script: it defines nothing from the exercise itself,
    imports nothing third-party, inlines its inputs, calls the code under test
    (assume the exercise code is prepended to it in the same file), PRINTS
    repr(result), asserts, and exits 0 on pass / raises AssertionError on fail.
11. The test MUST fail against buggy_code and pass against fixed_code, and it MUST
    assert on divergence_input (STEP 4). It targets the bug's observable behavior,
    not implementation details.
12. The test PRINTS repr(result) on exactly one line, immediately before the
    assertion, and prints nothing else. This is not optional: the sandbox reads
    that line as the executed result and checks it against your claimed
    buggy_result_on_divergence_input / fixed_result_on_divergence_input. Your
    claimed results MUST be exactly what repr() prints (0.1 not 0.10, None not
    "null", ['a', 'b'] with that spacing). If has_bug is false the test still
    prints repr(result) once, then asserts the correct behavior.
13. The ONLY failure the sandbox recognizes is AssertionError. If the bug
    manifests as some OTHER exception on the trigger input (allowed by constraint
    3), convert it: compute the result inside try/except and turn the exception
    into a sentinel value you can both print and assert against, so print(repr)
    still runs and the top-level failure is an AssertionError, never a raw
    exception.

    Worked example (a bug that raises on the trigger input):
      inventory = {"A1": 3, "B2": 0, "C3": 7}
      try:
          removed = drop_out_of_stock(inventory)
      except RuntimeError:
          removed = "RuntimeError"
      print(repr(removed))
      assert removed == ["B2"], "mutated the dict while iterating it"
    On buggy_code the call raises RuntimeError, caught and turned into the string
    sentinel (which fails the assert); on fixed_code it returns ["B2"] and passes.
    buggy_result_on_divergence_input would be "'RuntimeError'" (repr of the
    string), fixed_result_on_divergence_input "['B2']".

## Hard constraints on the answer options
14. Provide exactly 4 reason options: 1 correct, 3 distractors. If has_bug is
    false, the correct option is the "no bug" one and the 3 distractors are the
    things a careless reviewer would wrongly flag.
15. Every distractor must be FACTUALLY WRONG about this code in a way a careful
    reader can verify, yet tempting: it names a real Python pitfall this code
    happens not to have. Never make a distractor that is arguably also correct.
16. Randomize which option id (a-d) is correct. Do not always put it first.

## Output JSON (exactly this shape)
{
  "buggy_code": "<the code as shown to the user>",
  "fixed_code": "<identical to buggy_code except the minimal fix; if has_bug is false, identical>",
  "bug_lines": [<1-indexed line numbers in buggy_code that must change; [] if has_bug is false>],
  "bug_trigger_condition": "<STEP 3; omit if has_bug is false>",
  "divergence_input": "<STEP 3; omit if has_bug is false>",
  "buggy_result_on_divergence_input": "<exact repr() of buggy's result; omit if has_bug is false>",
  "fixed_result_on_divergence_input": "<exact repr() of fixed's result; MUST differ; omit if has_bug is false>",
  "divergence_justification": "<one sentence; omit if has_bug is false>",
  "test_code": "<standalone test per constraints 10-13; prints repr(result) then asserts>",
  "context_note": "<one sentence of production context, e.g. 'Runs once per order in the checkout worker.'>",
  "reason_options": [
    {"id": "a", "text": "<reason>"},
    {"id": "b", "text": "<reason>"},
    {"id": "c", "text": "<reason>"},
    {"id": "d", "text": "<reason>"}
  ],
  "correct_reason_id": "<a|b|c|d>",
  "draft_explanation": {
    "summary": "<2-4 sentences: what the bug is, why it happens, when it bites>",
    "principle": "<one sentence, the general rule to remember>",
    "line_notes": [{"line": <int>, "note": "<what this line actually does vs what it appears to do>"}]
  },
  "concepts": ["<the target concept slug from the Specification>"],
  "self_difficulty": <1-10, your honest estimate AFTER writing>,
  "self_check": {
    "single_bug_confirmed": <bool>,
    "runs_without_error_on_happy_path": <bool>,
    "no_hinting_names_or_comments": <bool>,
    "test_input_is_on_the_divergence_boundary": <bool>,
    "test_asserts_on_divergence_input": <bool>,
    "distractors_verifiably_wrong": <bool>
  }
}

## Specification (your assignment for THIS exercise)
- Python version: {{python_version}}
- Target concept (the bug's mechanism): {{concept}}
- Difficulty: {{difficulty}} on the 1-10 scale above
- Domain flavor: {{domain}}
- Code length: up to {{line_budget_max}} lines. Aim for roughly
  {{line_budget_min}}-{{line_budget_max}} lines where the bug realistically
  needs the room, but a minimal, clear bug may be shorter -- do NOT pad
  scaffolding to hit a line count. Readability, not length, is the target.
- has_bug: {{has_bug}}
- Do NOT reuse these bug mechanisms (recently used): {{avoid_patterns}}

Before emitting the JSON, re-read your own test: confirm it asserts on
divergence_input and that buggy_result_on_divergence_input differs from
fixed_result_on_divergence_input. If you cannot satisfy every constraint
simultaneously, output:
{"abort": true, "reason": "<why>"}
Aborting is always better than shipping a constraint violation.
================================= END USER ===================================

# ---------------------------------------------------------------------------
# Pipeline notes (NOT sent to the model)
#
# * self_check is not trusted; it exists because forcing the model to assert each
#   property measurably improves compliance. The REAL enforcement:
#     - B3 (schemas.py model_validator): a candidate whose
#       buggy_result_on_divergence_input == fixed_result_on_divergence_input is
#       rejected at SCHEMA VALIDATION -- zero tokens, zero sandbox. The divergence
#       fields are all-or-none; has_bug=false omits all five.
#     - B4 (sandbox_gate.validate_spot_the_bug, check stb_claim_matches_execution):
#       the D-11 pattern trace has always had, now for STB. The test prints
#       repr(result), so the buggy+test and fixed+test runs already capture the
#       ACTUAL results; the gate checks them against the model's claimed
#       buggy/fixed results and rejects on mismatch. Zero extra sandbox runs.
#       Skipped for pre-v4 candidates and has_bug=false (no divergence fields).
#     - buggy_fails_test / fixed_passes_test / determinism / diff-derived key
#       (D-49) are unchanged.
# * Static gate additionally rejects: forbidden imports/calls (AST walk), line
#   count OVER budget (buggy_code only, max-only since D-80), any comment
#   containing bug/fix/wrong/careful/note.
# * A sandbox-verified candidate from this template is also the seed for a
#   predict_the_fix exercise (D-80).
# * D-86: the `## Specification` block is LAST so the preceding content is a
#   stable prompt-cache prefix; the three former inline domain/concept references
#   now point at the Specification. {{python_version}} is a pinned constant.
# ---------------------------------------------------------------------------
