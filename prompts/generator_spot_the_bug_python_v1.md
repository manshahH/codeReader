# prompt_template_id: stb_py_v1
# Type: spot_the_bug | Language: Python {{python_version}} | Temp: 0.8
# System + user prompt below. Everything between BEGIN/END markers is sent to the model.

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
- Code length: {{line_budget_min}} to {{line_budget_max}} lines
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

## Hard constraints on the test
8. `test_code` is a standalone script: it defines nothing from the exercise itself,
   it imports nothing third-party, it inlines its inputs, calls the code under test
   (assume the exercise code is prepended to it in the same file), asserts, and
   exits 0 on pass / raises AssertionError on fail.
9. The test MUST fail against buggy_code and pass against fixed_code. It targets
   the bug's observable behavior, not implementation details.
10. If has_bug is false, the test simply passes against the code (it exists to
    prove the code is correct on the tricky-looking path).

## Hard constraints on the answer options
11. Provide exactly 4 reason options: 1 correct, 3 distractors, plus the pipeline
    adds nothing. If has_bug is false, the correct option is the "no bug" one and
    the 3 distractors are the things a careless reviewer would wrongly flag.
12. Every distractor must be FACTUALLY WRONG about this code in a way a careful
    reader can verify, yet tempting: it should name a real Python pitfall that
    this code happens not to have. Never make a distractor that is arguably
    also correct.
13. Randomize which option id (a-d) is correct. Do not always put it first.

## Output JSON (exactly this shape)
{
  "buggy_code": "<the code as shown to the user; if has_bug is false this is just the code>",
  "fixed_code": "<identical to buggy_code except the minimal fix; if has_bug is false, identical to buggy_code>",
  "bug_lines": [<1-indexed line numbers in buggy_code that must change; [] if has_bug is false>],
  "test_code": "<standalone test per constraints 8-10>",
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
# * Sandbox validation for this template:
#     1. exec(buggy_code + test_code)  -> must FAIL (AssertionError) [skip if !has_bug]
#     2. exec(fixed_code + test_code)  -> must PASS
#     3. exec(buggy_code) alone        -> must not raise (happy path import/run)
#     4. run each of the above twice; any stdout/exit difference = reject
#     5. diff(buggy_code, fixed_code) changed lines must equal bug_lines exactly
#        [if !has_bug: diff must be empty and bug_lines []]
# * If has_bug is false, correct_reason_id must point at the option whose text
#   asserts the code is correct; pipeline verifies that option exists.
# * Static gate additionally rejects: forbidden imports/calls (AST walk), line
#   count out of budget, any comment containing bug/fix/wrong/careful/note.
# ---------------------------------------------------------------------------
