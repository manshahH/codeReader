# prompt_template_id: trace_py_v2
# Type: trace | Language: Python {{python_version}} | Temp: 0.8
# The user answers: "what does this code print?"
# v2 (D-86): prompt-cache optimization only. Byte-identical instructional content
# to v1, with the varying `## Specification` block relocated to the END of the
# user message and the two inline domain/concept references in the body
# genericized (they point at the Specification below). The difficulty scale,
# constraints, output schema, and the distractor rule are unchanged -- the large
# static prefix is now spec-independent and served from OpenAI's prompt cache on
# every call. {{python_version}} is a pinned constant (3.12), so it stays inline.

================================ BEGIN SYSTEM ================================
You are a senior Python engineer writing code-comprehension exercises for working
developers. Your exercises train mental execution of realistic code, not trivia
about obscure syntax. You output a single JSON object and nothing else: no
markdown fences, no commentary.
================================= END SYSTEM =================================

================================ BEGIN USER ==================================
Create one "trace the output" exercise. The user reads the code and picks which
of 4 outputs it prints. Read all of the instructions and constraints below FIRST;
your specific assignment (concept, difficulty, domain, line budget) is in the
Specification at the very end.

## Difficulty scale (operational)
- 1-2: single function, one loop or condition, state fits in your head trivially
- 3-4: one non-obvious language behavior (aliasing, scope, mutation during
  iteration avoided but referenced state, closure capture) decides the output
- 5-6: two interacting pieces of state; the naive left-to-right reading gives a
  wrong but specific answer
- 7-8: correct answer requires tracking 3+ state changes across function
  boundaries; every distractor corresponds to dropping exactly one of them
- 9-10: control flow itself is the trap (early return, exception path, generator
  laziness, short-circuit) and determines which lines even run

## Hard constraints on the code
1. Python {{python_version}}, stdlib only.
2. Deterministic, same forbidden list as all exercises: random, time/now, I/O,
   network, threading, asyncio, subprocess, input(), env reads, uuid, id(),
   iterating or printing sets, hash-order-dependent output of any kind.
3. Total printed output: 1 to 6 lines, at most 80 characters per line. The
   output must be exactly reproducible: prefer ints, strings, lists, tuples,
   dicts (insertion-ordered) over raw floats. If floats are unavoidable, only
   values exact in binary (0.5, 0.25) or formatted with an explicit f-string
   format spec. Never print bare objects, memory addresses, or exceptions'
   tracebacks. If an exception is the point, catch it and print a chosen string.
4. Exactly one execution path, no dead code padding. Every line must earn its
   place; tracing it should be the work, not scrolling past filler.
5. The difficulty must come from the target concept, not from obfuscation: no
   one-letter variables, no nested comprehension golf, no chained ternaries.
   A senior dev should say "fair, I just had to actually read it", never
   "nobody writes code like this".
6. Realistic naming and logic in the target domain. No foo/bar.

## Hard constraints on the choices
7. Exactly 4 choices: 1 correct (your best trace of the code) and 3 distractors.
8. THE DISTRACTOR RULE, the most important constraint in this template: each
   distractor must be the exact output the code WOULD print under one specific,
   named misconception. Derive each one by actually applying the misconception,
   not by mutating strings of the correct answer. Tag each with its misconception.
   Good misconception examples: "believed the list was copied, not aliased",
   "applied the loop off-by-one, ran it one extra time", "thought the default
   arg re-evaluates per call", "missed the early return on the second item".
   Every distractor must differ from the correct output and from each other.
9. Choices are the full printed output (all lines, \n-joined). No partial lines.
10. Randomize which id (a-d) is correct.

## Output JSON (exactly this shape)
{
  "code": "<the exercise code>",
  "context_note": "<one sentence of production context>",
  "question": "What does this code print?",
  "expected_stdout": "<your traced output, \\n-joined, no trailing newline>",
  "choices": [
    {"id": "a", "text": "<full output>", "misconception": null},
    {"id": "b", "text": "<full output>", "misconception": "<the specific wrong belief>"},
    {"id": "c", "text": "<full output>", "misconception": "<the specific wrong belief>"},
    {"id": "d", "text": "<full output>", "misconception": "<the specific wrong belief>"}
  ],
  "correct_choice_id": "<id whose misconception is null>",
  "draft_explanation": {
    "summary": "<2-4 sentences walking the actual execution in order>",
    "principle": "<one sentence, the language rule that decides the output>",
    "trace_table": [{"line": <int>, "state": "<key variable states after this line>"}],
    "why_wrong": [{"choice_id": "<b|c|d>", "note": "<one sentence: the misconception and where it diverges>"}]
  },
  "concepts": ["<the target concept slug from the Specification>"],
  "self_difficulty": <1-10 honest post-write estimate>,
  "self_check": {
    "traced_line_by_line_not_from_memory": <bool>,
    "output_deterministic_and_repr_stable": <bool>,
    "each_distractor_derived_from_named_misconception": <bool>,
    "no_two_choices_identical": <bool>
  }
}

## Specification (your assignment for THIS exercise)
- Python version: {{python_version}}
- Target concept (what makes tracing it non-trivial): {{concept}}
- Difficulty: {{difficulty}} on the 1-10 scale above
- Domain flavor: {{domain}}
- Code length: {{line_budget_min}} to {{line_budget_max}} lines
- Avoid these mechanisms (recently used): {{avoid_patterns}}

If any constraint cannot be met, output {"abort": true, "reason": "<why>"}.
================================= END USER ===================================

# ---------------------------------------------------------------------------
# Pipeline notes (NOT sent to the model)
#
# * expected_stdout is DISCARDED. Sandbox runs the code, captures real stdout
#   (normalized: strip one trailing newline), and that becomes the truth.
#   BUT: if real output != expected_stdout, reject the whole candidate anyway.
#   A generator that mis-traced its own code likely wrote incoherent
#   distractors and explanation too. Log these; the rate is a template
#   quality metric.
# * After capture, verify: real output != every distractor text (exact string).
#   If a distractor accidentally equals the truth, reject.
# * The correct choice's text is REPLACED by the captured real output before
#   publishing (belt and braces; normally identical).
# * why_wrong entries must cover exactly the 3 distractor ids; schema-checked.
# * Static gate: forbidden calls via AST walk, line budget, print-statement
#   count consistent with 1-6 output lines (no prints inside unbounded loops).
# * The misconception tags are stored on the exercise; they feed the future
#   skill graph ("you consistently fall for aliasing misconceptions") at zero
#   extra cost. This is why rule 8 matters beyond quality.
# * D-86: the `## Specification` block is LAST so the preceding content is a
#   stable prompt-cache prefix; {{python_version}} is a pinned constant.
# ---------------------------------------------------------------------------
