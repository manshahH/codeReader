# prompt_template_id: stb_py_v3
# Type: spot_the_bug | Language: Python {{python_version}} | Temp: 0.8
# System + user prompt below. Everything between BEGIN/END markers is sent to the model.
# v3 (D-80): adds a complete worked buggy/fixed/test/bug_lines triple teaching
# TEST-INPUT SELECTION on the divergence boundary (constraint 11) -- the
# dominant STB reject was a test that does not discriminate: a real bug is
# planted, then inputs are chosen where buggy and fixed produce IDENTICAL
# output, so the assertion never fires and buggy+test exits 0. Abstract rules
# do not land with this model; a full worked example does. v3 also softens the
# code-length line to MAX-only (D-80: the min was almost pure false-reject).
# Carries forward v2's insertion+replace and exception-to-assertion worked
# examples unchanged.

================================ BEGIN SYSTEM ================================
You are a senior Python engineer writing code-comprehension exercises for working
developers. Your exercises are realistic production code, not puzzles. You output
a single JSON object and nothing else: no markdown fences, no commentary.
================================= END SYSTEM =================================

================================ BEGIN USER ==================================
Create one "spot the bug" exercise.

## Specification
- Python version: {{python_version}}
- Target concept (the bug's mechanism): {{concept}}
- Difficulty: {{difficulty}} on the 1-10 scale defined below
- Domain flavor: {{domain}}
- Code length: up to {{line_budget_max}} lines. Aim for roughly
  {{line_budget_min}}-{{line_budget_max}} lines where the bug realistically
  needs the room, but a minimal, clear bug may be shorter -- do NOT pad
  scaffolding to hit a line count. Readability, not length, is the target.
- has_bug: {{has_bug}}
- Do NOT reuse these bug mechanisms (recently used): {{avoid_patterns}}

## Difficulty scale (operational, not vibes)
- 1-2: bug visible in a single line once you look at it; common junior mistake
- 3-4: bug requires reading 2-3 functions together or tracking one variable's lifecycle
- 5-6: bug is a correct-looking pattern that fails on a specific input class or call
  sequence; requires mentally executing the code
- 7-8: bug is an interaction between two components that are each individually correct
- 9-10: bug survives a plausible test suite; only a precise edge case exposes it

## Hard constraints on the code
1. Runs on Python {{python_version}}, stdlib only, no third-party imports.
2. Deterministic. FORBIDDEN anywhere in the code: random, time, datetime.now,
   os/sys interaction beyond argv-free execution, file I/O, network, threading,
   asyncio, subprocess, input(), environment reads, uuid, id()-dependent logic,
   iterating or printing sets, relying on dict ordering other than insertion order.
3. The buggy code MUST run without raising on the happy path. The bug is semantic:
   wrong value, wrong state, wrong behavior on an input class. Never a SyntaxError,
   NameError, or missing import. Exception-raising bugs are allowed only if the
   exception occurs on a non-obvious input, not on every call.
4. EXACTLY ONE bug if has_bug is true. Before finalizing, re-read your buggy code
   line by line hunting for accidental second defects (off-by-one you did not
   intend, resource issues, edge cases in YOUR scaffolding code). Scaffolding must
   be boring and correct.
5. If has_bug is false: the code is correct, and it must LOOK suspicious enough
   that a careless reviewer would flag something. Use patterns that are commonly
   believed buggy but are correct in this context.
6. No comments, docstrings, or names that hint at the bug or its absence. Names
   like `broken_total` or comments like `# careful here` are automatic rejects.
   Write the comments a normal engineer would write, which is: few.
7. Realistic {{domain}} code: real-looking entity names, plausible logic. No
   foo/bar, no lottery-ticket toy examples.
8. fixed_code must be a minimal, natural edit of buggy_code: change only what
   the bug actually requires, the way a competent engineer would actually fix
   it. Every line NOT listed in bug_lines MUST be byte-identical between
   buggy_code and fixed_code, but the fix is free to INSERT new lines (a new
   import, a new guard clause, wrapping existing code in a `with`/`try`
   block) or DELETE lines outright -- the sandbox gate diffs buggy_code
   against fixed_code and only charges bug_lines with lines the fix actually
   REPLACES or DELETES; a line the fix purely INSERTS shifts nothing and
   costs nothing. Do NOT contort buggy_code to pre-plant an unused or
   misused import/field/lock "just so the fix avoids adding a line" --
   dead scaffolding is itself a tell, and if the concept's natural fix needs
   an import that's on the forbidden list (`threading`, `time`, etc.), the
   fix cannot use that mechanism at all, planted or not. The one requirement
   an insertion-heavy fix must still satisfy: at least one line that exists
   in buggy_code must have its own text actually replaced by the fix. A fix
   that is 100% new lines, with no existing line's text ever changing, gives
   bug_lines == [] (indistinguishable from has_bug=false) and will fail
   review even if the sandbox gate lets it through -- there must be a
   specific line the exercise is pointing at.

   Worked example (insertion alongside a real change is fine and common):
     buggy_code:
       1  def apply_late_fee(balance, days_late):
       2      fee = balance * 0.02 * days_late
       3      return balance + fee
     fixed_code:
       1  def apply_late_fee(balance, days_late):
       2      max_fee = balance * 0.5
       3      fee = min(balance * 0.02 * days_late, max_fee)
       4      return balance + fee
     Here line 1 and the old line 3 (now line 4) are untouched; a new line 2
     was INSERTED and old line 2's text was REPLACED (now line 3). bug_lines
     is [2] -- buggy_code's own line number for the line whose text changed.
     The inserted line costs nothing; the replaced line is what bug_lines
     names.
9. bug_lines must be computed, not estimated, and must reflect a REAL diff,
   not a naive position-by-position comparison. After writing buggy_code and
   fixed_code, align them the way a text diff would (matching unchanged lines
   by content, not by index) and record the buggy_code line numbers (1-indexed)
   that the alignment marks as replaced or deleted. Lines the fix only inserts
   are never in bug_lines. If a line shifted position because an earlier line
   was inserted or deleted, that shift alone does not put it in bug_lines --
   only lines whose own text actually changed do. If has_bug is false,
   bug_lines must be [] and fixed_code must be byte-for-byte identical to
   buggy_code -- never "improve" or "correct" anything in fixed_code when
   has_bug is false, even something that looks fixable.

## Hard constraints on the test
10. `test_code` is a standalone script: it defines nothing from the exercise itself,
    it imports nothing third-party, it inlines its inputs, calls the code under test
    (assume the exercise code is prepended to it in the same file), asserts, and
    exits 0 on pass / raises AssertionError on fail.
11. The test MUST fail against buggy_code and pass against fixed_code. It targets
    the bug's observable behavior, not implementation details. This is only
    possible if you feed the code THE INPUT WHERE THE TWO VERSIONS DIVERGE.
    A real bug still produces the SAME output as the fix on most inputs; it
    misbehaves only on a specific input class (the boundary value, the empty
    collection, the duplicate key, the negative number, the second call).
    Choose your test input so that buggy_code returns X and fixed_code returns
    a DIFFERENT Y, then assert Y. If your buggy and fixed code produce the same
    result on the input you picked, the assertion never fires, buggy+test exits
    0, and the exercise is worthless and will be rejected -- the planted bug is
    real but the test does not catch it.

    Worked example (choosing the input on the divergence boundary):
      buggy_code (an off-by-one on a threshold: `>` where the spec says "at
      least 100"):
        1  def tier_discount(order_total):
        2      if order_total > 100:
        3          return 0.10
        4      return 0.0
      fixed_code:
        1  def tier_discount(order_total):
        2      if order_total >= 100:
        3          return 0.10
        4      return 0.0
      bug_lines: [2]
      The two versions DIVERGE only at order_total == 100: buggy returns 0.0,
      fixed returns 0.10. At 150 both return 0.10; at 50 both return 0.0 --
      those inputs are OFF the divergence boundary and a test using only them
      passes on buggy code too (the classic worthless test). So the test picks
      exactly the boundary:
      test_code:
        order_total = 100
        assert tier_discount(order_total) == 0.10, "spend of exactly 100 should earn the discount"
      Run it in your head against BOTH versions before finalizing: buggy
      returns 0.0 (AssertionError -> the test fails, good) and fixed returns
      0.10 (passes, good). If you cannot state, for your chosen input, the two
      DIFFERENT values buggy and fixed return, you have not found the
      divergence boundary yet -- keep looking or the exercise is invalid.
12. If has_bug is false, the test simply passes against the code (it exists to
    prove the code is correct on the tricky-looking path).
13. The ONLY failure the sandbox recognizes as a legitimate test failure is
    AssertionError. If the bug manifests as some OTHER exception on the trigger
    input (allowed by constraint 3), the test must not let that exception
    propagate: wrap the triggering call and convert it.

    Worked example (a bug that raises RuntimeError when exercised):
      inventory = {"A1": 3, "B2": 0, "C3": 7}
      try:
          removed = drop_out_of_stock(inventory)
      except RuntimeError:
          raise AssertionError("mutated the dict while iterating it")
      assert removed == ["B2"]
      assert inventory == {"A1": 3, "C3": 7}
    On buggy_code the call raises RuntimeError, which the test converts to
    AssertionError (a legitimate failure); on fixed_code the call returns
    normally and the remaining asserts run. A non-AssertionError exception
    reaching the top level of the test is treated as a broken candidate, not
    a failing test.

## Hard constraints on the answer options
14. Provide exactly 4 reason options: 1 correct, 3 distractors, plus the pipeline
    adds nothing. If has_bug is false, the correct option is the "no bug" one and
    the 3 distractors are the things a careless reviewer would wrongly flag.
15. Every distractor must be FACTUALLY WRONG about this code in a way a careful
    reader can verify, yet tempting: it should name a real Python pitfall that
    this code happens not to have. Never make a distractor that is arguably
    also correct.
16. Randomize which option id (a-d) is correct. Do not always put it first.

## Output JSON (exactly this shape)
{
  "buggy_code": "<the code as shown to the user; if has_bug is false this is just the code>",
  "fixed_code": "<identical to buggy_code except the minimal fix; if has_bug is false, identical to buggy_code>",
  "bug_lines": [<1-indexed line numbers in buggy_code that must change; [] if has_bug is false>],
  "test_code": "<standalone test per constraints 10-13>",
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
  "concepts": ["{{concept}}"],
  "self_difficulty": <1-10, your honest estimate AFTER writing, may differ from the spec>,
  "self_check": {
    "single_bug_confirmed": <bool>,
    "runs_without_error_on_happy_path": <bool>,
    "no_hinting_names_or_comments": <bool>,
    "test_input_is_on_the_divergence_boundary": <bool>,
    "distractors_verifiably_wrong": <bool>
  }
}

If you cannot satisfy every constraint simultaneously, output:
{"abort": true, "reason": "<why>"}
Aborting is always better than shipping a constraint violation.
================================= END USER ===================================

# ---------------------------------------------------------------------------
# Pipeline notes (NOT sent to the model)
#
# * The self_check block is not trusted; it exists because forcing the model to
#   assert each property measurably improves compliance. Gates still verify.
#   test_input_is_on_the_divergence_boundary is new in v3 (D-80): the sandbox
#   gate's buggy_fails_test check IS the real enforcement -- a test that does
#   not discriminate makes buggy+test exit 0, which fails buggy_fails_test.
# * Sandbox validation for this template:
#     1. exec(buggy_code + "\n"? + test_code) -> must FAIL (AssertionError)
#        [skip if !has_bug; the gate inserts the newline separator itself if
#        the code does not end with one, D-50]
#     2. exec(fixed_code + test_code)  -> must PASS
#     3. exec(buggy_code) alone        -> must not raise (happy path import/run)
#     4. run each of the above twice; any stdout/exit difference = reject
#     5. the answer key is DERIVED (D-49): the buggy_code lines the fix
#        replaces or deletes in a real diff become verified_bug_lines. The
#        model's declared bug_lines are compared and logged as a template
#        quality metric, never a reject. Rejected only when the diff is empty
#        (pure insertion, has_bug=true) or rewrite-sized (over the minimal-fix
#        cap). [if !has_bug: fixed_code byte-identical and bug_lines []]
# * If has_bug is false, correct_reason_id must point at the option whose text
#   asserts the code is correct; pipeline verifies that option exists.
# * Static gate additionally rejects: forbidden imports/calls (AST walk), line
#   count OVER budget (buggy_code only, max-only since D-80), any comment
#   containing bug/fix/wrong/careful/note.
# * A sandbox-verified candidate from this template is also the seed for a
#   predict_the_fix exercise (D-80): its (buggy, fixed, test) triple is reused
#   directly, with 3 execution-verified wrong-fix distractors added.
# ---------------------------------------------------------------------------
