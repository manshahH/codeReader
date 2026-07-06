# prompt_template_ids: gate_solver_v1, gate_defect_audit_v1, gate_reasons_v1
# Run at temperature 0, on a DIFFERENT model/family than the generator.
# All three receive ONLY what they need; none ever sees the generator's answers
# except where explicitly stated. Order: defect_audit -> solver -> reasons.

===========================================================================
## GATE 1: gate_defect_audit_v1  (spot_the_bug only)
Purpose: enforce "exactly one bug" (or "zero bugs" when has_bug=false).
Input: buggy_code ONLY. Not the fix, not the intended bug, not the options.
===========================================================================

BEGIN PROMPT
You are auditing a piece of Python {{python_version}} code for defects. List
EVERY defect you can find: logic errors, edge-case failures, incorrect state
handling, resource misuse. Do not list style issues, naming, missing type
hints, or hypothetical improvements. A defect is something that produces wrong
behavior for some realistic input or call pattern.

For each defect give: the line number(s), one-sentence description, and a
concrete input or call sequence that exposes it.

Output JSON only:
{"defects": [{"lines": [<int>], "description": "<...>", "exposed_by": "<...>"}]}
If there are no defects: {"defects": []}

<code>
{{buggy_code}}
</code>
END PROMPT

Pipeline decision rule:
- has_bug=true: PASS iff exactly one defect is reported AND its lines overlap
  bug_lines. Two defects reported = reject (accidental second bug, the number
  one dispute source). Zero reported = flag for human review (either the bug is
  excellent or the exercise is broken; a human decides which).
- has_bug=false: PASS iff defects is empty. Any reported defect = reject or
  human review if the report looks wrong.
- The "exposed_by" field of the confirmed defect is stored; it becomes free
  material for the explanation writer.

===========================================================================
## GATE 2: gate_solver_v1  (both types)
Purpose: cold-solve the exercise exactly as a user would; catches ambiguity,
unfairness, and mis-keyed answers.
Input: the user-visible payload ONLY (code, context_note, options/choices).
Never the answer key.
===========================================================================

BEGIN PROMPT
You are a strong senior Python developer taking a code-reading exercise. Solve
it exactly as presented. Think carefully, then commit to one answer.

Output JSON only:
{
  "answer": <for spot_the_bug: {"line": <int>, "reason_id": "<a-d>"} |
             for trace: {"choice_id": "<a-d>"}>,
  "confidence": <0.0-1.0>,
  "problems_with_the_exercise": ["<only if something is genuinely ambiguous,
    underspecified, or has multiple defensible answers; empty list otherwise>"]
}

<exercise>
{{payload_json}}
</exercise>
END PROMPT

Pipeline decision rule:
- PASS iff the solver's answer matches the key AND problems list is empty.
- Solver wrong at confidence >= 0.8: reject; the exercise is probably unfair
  or mis-keyed (a confident strong model failing usually means the exercise is
  at fault, not the model).
- Solver wrong at confidence < 0.8: human review with the solver transcript
  attached; this is often a legitimately hard difficulty 7+ exercise, which is
  exactly what you want to keep, but a human confirms.
- Any non-empty problems list: human review regardless of correctness.
- Record solver_correct as a feature for the empirical difficulty prior.

===========================================================================
## GATE 3: gate_reasons_v1  (spot_the_bug only)
Purpose: verify each distractor reason is definitively wrong for THIS code,
and the correct reason is precise. Execution cannot check prose; this can.
Input: buggy_code + the four reason options. Not which one is keyed correct.
===========================================================================

BEGIN PROMPT
Below is Python code containing a known defect, and four candidate explanations
of what is wrong with it. For EACH candidate, classify it:

- "correct": accurately identifies the actual defect and its mechanism
- "wrong": claims something about this code that is factually false or
  describes a pitfall this code does not have
- "partially_defensible": not the intended-sounding answer, but a careful
  reader could legitimately argue it is also true of this code

Judge each option independently against the code. Output JSON only:
{"verdicts": [{"id": "a", "classification": "<...>", "justification": "<one sentence>"}, ...]}

<code>
{{buggy_code}}
</code>
<options>
{{reason_options_json}}
</options>
END PROMPT

Pipeline decision rule:
- PASS iff exactly one option is classified "correct", it matches
  correct_reason_id, and zero options are "partially_defensible".
- Any "partially_defensible" = reject. A distractor that is arguably right is
  worse than a broken test: it fails your most careful users, the exact people
  who write disputes and HN comments.
- Two options "correct" = reject (options overlap in meaning).

===========================================================================
# Cross-gate notes
# * Gates never repair. Reject means regenerate from spec, per README retry
#   policy.
# * Every gate verdict JSON is stored in the validation report (S3) referenced
#   by exercises.validation_report_url, so human review and dispute handling
#   always have the receipts.
# * Gate model must differ from generator model: a model grading its own
#   output inherits its own blind spots. If the generator is Claude, gate with
#   a different family, or minimum a different Claude tier, and note which in
#   the validation report.
===========================================================================
