# 01 : Content Specification

Content is the make-or-break subsystem. Everything here exists to guarantee one
invariant:

> **No exercise ships unless its ground truth was produced or confirmed by
> execution, never by an LLM's claim.**

## Exercise envelope (one schema, type-specific payload)

```json
{
  "id": "uuid",
  "version": 3,
  "type": "spot_the_bug | trace | summarize | ...",
  "language": "python",
  "language_version": "3.12",
  "difficulty": { "authored": 4, "empirical": null },
  "concepts": ["mutable-default-arg"],
  "tags": ["backend", "stdlib-only"],
  "est_time_s": 90,
  "source": { "origin": "llm|oss_bug|oss_snippet|community",
              "model": "...", "prompt_template_id": "stb_py_v1",
              "repo": null, "commit": null, "license": null, "attribution": null },
  "payload": { },        // what the client sees BEFORE answering
  "grading": { },        // answer key / rubric; NEVER leaves the server pre-answer
  "explanation": { },    // revealed only in the grade response
  "lifecycle": { "status": "draft|in_review|live|pulled|retired",
                 "validated_at": "...", "validation_report_id": "...",
                 "human_reviewed": true, "dispute_count": 0 }
}
```

Rules:
- Exercises are IMMUTABLE per version. Any fix bumps version; stats attach to
  (id, version).
- `source` is mandatory. OSS-origin content must carry repo, commit, license
  (MIT/Apache-2.0/BSD only), and attribution text, rendered in the UI.
- Two difficulty numbers: authored (LLM prior) and empirical (computed from
  live solve rates, overrides authored once n >= 50).

## Payload/grading shapes (MVP types)

spot_the_bug payload: code, context_note, answer_mode
"line_select_plus_reason", reason_options[4]. Grading: mode deterministic,
correct_lines, correct_reason_id, artifacts {failing_test, fixed_code_hash,
test results both legs}.

trace payload: code, context_note, question, choices[4] (each choice may carry
a misconception tag, stored server-side). Grading: correct_choice_id where the
correct text is the SANDBOX-CAPTURED stdout.

summarize payload: code, max_words. Grading: mode rubric, rubric
{must_mention[] weighted, must_not_claim[], pass_threshold}, reference_answer.

## Validation invariants per type
- trace: correct output = captured stdout from execution; generator's claim
  discarded (but disagreement with the claim rejects the candidate entirely).
- spot_the_bug / predict_the_fix: twin-snippet invariant. Possess (buggy,
  fixed, test) where the test FAILS on buggy and PASSES on fixed, both proven
  by execution. has_bug=false variant: diff empty, test passes, defect audit
  finds zero defects.
- summarize: no execution oracle; two-model protocol + 100% human review at MVP.

## Pipeline stages
```
SPEC SAMPLER -> GENERATOR -> STATIC GATE -> SANDBOX GATE -> SEMANTIC GATES -> DEDUP -> EXPLAIN -> REVIEW QUEUE -> SHADOW RELEASE -> LIVE
```
1. Spec sampler: samples (concept, difficulty, type, domain, line budget,
   has_bug, avoid_patterns) from the controlled taxonomy. The sampler owns the
   curriculum distribution, not the LLM.
2. Generator: templates in /prompts, temp 0.8, JSON-only output, single-retry
   on parse failure only.
3. Static gate: AST parse, forbidden imports/calls (random, time, io, network,
   threading, sets iteration, ...), line budget, hinting names/comments,
   secrets/profanity.
4. Sandbox gate: Docker, --network=none, read-only fs, 128MB, 0.5 CPU, 5s
   wall. Run EVERYTHING twice; any output difference rejects
   (nondeterminism). Implements the per-type invariants above. Reference
   implementation of the STB rules: /prompts/dryrun_stb_validation.py (proven
   by execution, including a negative test).
5. Semantic gates (temp 0, DIFFERENT model family than generator, prompts in
   /prompts/gates_v1.md): defect audit (exactly-one-bug), cold solver,
   reason-distractor verification. Gates never repair; reject = regenerate
   fresh from spec (max 3 attempts per spec).
6. Dedup: AST-normalized (identifiers/literals/comments stripped) exact hash,
   then embedding cosine > 0.92 vs live pool rejects.
7. Explanation writer: runs AFTER validation with verified artifacts in
   context; must cite line numbers, state principle + instance.
8. Human review: 100% until 500 live exercises; approve / fix-and-bump /
   kill via review CLI. Budget 60-90s per exercise (review = verifying
   receipts, not re-deriving).
9. Shadow release: status live but flagged calibrating; after ~50 attempts
   compute empirical difficulty; auto-flag if solve rate <10% or >98% or
   dispute rate >2% (MVP: alert + manual pull).

## OSS real-bug track (post-MVP)
Mine merged bugfix commits (small diff, adds a test) from MIT/Apache/BSD repos
verified via GitHub license API; pre-fix code + the added test = exercise with
real-world ground truth; twin-snippet validated in sandbox; LLM may only
DELETE lines for brevity, then both test legs re-run. Yield ~1 per 30
candidate commits; feeds the weekly flagship, not daily volume.

## Cost model
~$0.05-0.15 per candidate through all gates, ~20-30% end-to-end survival
(D-56; realistic for this execution-verified gate design once the per-stage
pass rates are compounded -- trace claim-match and the semantic judges are
strict on purpose), so roughly $0.20-0.75 per shipped exercise at those
per-candidate prices, and well under that with a gpt-4.1-class generator.
200-exercise MVP corpus: on the order of $50-150 plus review time.
Validation is cheap enough to be ruthless: reject aggressively and generate
more; never loosen a correct gate to chase yield.

## Concept taxonomy
Controlled, versioned vocabulary, ~40 concepts for Python v1 (mutable state,
off-by-one, aliasing, closure capture, error handling, resource leaks,
timezone/encoding, N+1, injection, concurrency-conceptual, ...). Lives in
pipeline/taxonomy.py as code, version-stamped onto exercises. Drives the spec
sampler, spaced repetition, and the skill graph; free-form `tags` is the
overflow field.
