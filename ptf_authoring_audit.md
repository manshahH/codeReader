# predict_the_fix authoring audit (read-only)

Purpose: the exact contract a hand-authored `predict_the_fix` (PTF) batch must
satisfy, quoted verbatim from the real source, so a batch can be authored the
way `pipeline/handauthored_stb_batch*.json` was for `spot_the_bug`. No files
were changed to produce this document.

---

## A. SCHEMA — `pipeline/schemas.py`

The generator-output schema for PTF is narrow: it covers ONLY the 3 wrong-fix
distractors. There is no schema for the "full" PTF exercise (buggy/fixed/test
triple + distractors) anywhere in the codebase today — that triple is always
an `STBCandidate`, borrowed from the upstream spot_the_bug.

```python
class PredictFixVariant(BaseModel):
    model_config = _STRICT

    code: str
    note: str


class PredictFixCandidate(BaseModel):
    """Generator output for predict_the_fix (D-80): ONLY the 3 wrong-fix
    distractors. The correct choice is the upstream spot_the_bug candidate's
    execution-verified fixed_code, never anything in this object. Every variant
    here is re-executed against the test in the sandbox and must STILL FAIL.
    """

    model_config = _STRICT

    wrong_fixes: list[PredictFixVariant] = Field(min_length=3, max_length=3)
```

(`pipeline/schemas.py:133-149`)

Where `_STRICT = ConfigDict(extra="forbid")` (`pipeline/schemas.py:26`) — applies
to both models. So:

- `PredictFixVariant`: exactly two fields, `code: str` and `note: str`. No
  defaults, no optional fields, extra keys forbidden.
- `PredictFixCandidate`: exactly one field, `wrong_fixes`, constrained to
  **exactly 3** entries (`Field(min_length=3, max_length=3)` — not "at least
  3", not "up to 4"). No `model_validator` on either class — all correctness
  checks for PTF live in the sandbox gate (section B), not in schema
  validation, unlike `STBCandidate`'s `_divergence_fields_all_or_none_and_
  discriminating` validator or `TraceCandidate`'s `_why_wrong_covers_exactly_
  the_distractors` validator. PTF has neither.

The triple a PTF is derived from is the existing `STBCandidate`
(`pipeline/schemas.py:77-102`), reproduced here because any hand-authored PTF
batch has to supply fields shaped like this even though there's no dedicated
PTF-triple schema:

```python
class STBCandidate(BaseModel):
    model_config = _STRICT

    buggy_code: str
    fixed_code: str
    bug_lines: list[int]
    test_code: str
    context_note: str
    reason_options: list[ReasonOption] = Field(min_length=4, max_length=4)
    correct_reason_id: str
    draft_explanation: STBDraftExplanation
    concepts: list[str] = Field(min_length=1)
    self_difficulty: int = Field(ge=1, le=10)
    self_check: STBSelfCheck
    bug_trigger_condition: str | None = None
    divergence_input: str | None = None
    buggy_result_on_divergence_input: str | None = None
    fixed_result_on_divergence_input: str | None = None
    divergence_justification: str | None = None
```

(`pipeline/schemas.py:77-102`)

Only `buggy_code`, `fixed_code`, and `test_code` off this model actually reach
the PTF sandbox gate — `pipeline.predict_the_fix.derive_artifacts` reads
exactly those three attributes off whatever `stb_candidate` object it's
handed (see section C); it never touches `reason_options`,
`correct_reason_id`, `draft_explanation`, `self_check`, `self_difficulty`, or
the divergence fields. `concepts` IS read (`derive_artifacts`'s caller passes
`concepts=list(stb_candidate.concepts)` into `insert_predict_the_fix` —
section C/F).

---

## B. THE SANDBOX GATE — `pipeline/sandbox_gate.py`, `validate_predict_the_fix`

Full function, verbatim:

```python
def validate_predict_the_fix(
    *,
    buggy_code: str,
    fixed_code: str,
    test_code: str,
    wrong_fixes: list[str],
) -> SandboxGateResult:
    """predict_the_fix gate (D-80). The correct choice is the upstream STB's
    execution-verified fixed_code; this proves, by execution, that (a) that fix
    really does pass the test, (b) the buggy code really does fail it (its
    output becomes the payload's failing-test output), and (c) every wrong-fix
    distractor STILL FAILS the test -- the new invariant. A distractor that
    PASSES is a second correct answer and rejects the candidate; a distractor
    that fails with anything other than AssertionError is broken code, not a
    plausible fix, and also rejects. Distractors must be textually distinct
    from buggy_code, fixed_code, and each other, so no choice is a duplicate or
    the unchanged original.
    """
    checks: list[GateCheck] = []

    # 1. Correct choice: fixed_code + test PASSES (re-affirmed here so the gate
    #    is self-contained; the STB gate already proved it upstream).
    fixed_run_a = run_python(_concat_snippets(fixed_code, test_code))
    fixed_run_b = run_python(_concat_snippets(fixed_code, test_code))
    ok_fixed = fixed_run_a.exit_code == 0
    checks.append(GateCheck("correct_fix_passes_test", ok_fixed, fixed_run_a.stderr[-500:]))

    # 2. buggy_code + test FAILS with AssertionError; capture the failure output
    #    for the payload's "failing test output".
    buggy_run_a = run_python(_concat_snippets(buggy_code, test_code))
    buggy_run_b = run_python(_concat_snippets(buggy_code, test_code))
    ok_buggy = buggy_run_a.exit_code != 0 and "AssertionError" in buggy_run_a.stderr
    checks.append(GateCheck("buggy_fails_test", ok_buggy, buggy_run_a.stderr[-500:]))
    captured_test_output = buggy_run_a.stderr if ok_buggy else None

    det = (
        (fixed_run_a.exit_code, fixed_run_a.stdout, fixed_run_a.stderr)
        == (fixed_run_b.exit_code, fixed_run_b.stdout, fixed_run_b.stderr)
        and (buggy_run_a.exit_code, buggy_run_a.stdout, buggy_run_a.stderr)
        == (buggy_run_b.exit_code, buggy_run_b.stdout, buggy_run_b.stderr)
    )

    # 3. Each wrong fix must STILL FAIL the test (AssertionError), deterministically.
    for i, wrong in enumerate(wrong_fixes):
        run_a = run_python(_concat_snippets(wrong, test_code))
        run_b = run_python(_concat_snippets(wrong, test_code))
        still_fails = run_a.exit_code != 0 and "AssertionError" in run_a.stderr
        checks.append(
            GateCheck(
                f"distractor_{i}_still_fails_test",
                still_fails,
                # A passing distractor (exit 0) is the failure this gate exists
                # to catch: it is not wrong, so it cannot be a distractor.
                f"exit={run_a.exit_code} {run_a.stderr[-300:]}",
            ),
        )
        det = det and (run_a.exit_code, run_a.stdout, run_a.stderr) == (
            run_b.exit_code,
            run_b.stdout,
            run_b.stderr,
        )

    checks.append(GateCheck("deterministic_double_run", det))

    # 4. Distractors distinct from each other, from buggy_code, and from fixed_code.
    normalized = [w.strip() for w in wrong_fixes]
    reference = {buggy_code.strip(), fixed_code.strip()}
    distinct = len(set(normalized)) == len(normalized) and not (set(normalized) & reference)
    checks.append(
        GateCheck(
            "distractors_distinct",
            distinct,
            "each wrong fix must differ from buggy_code, fixed_code, and the others",
        ),
    )

    accepted = all(c.passed for c in checks)
    return SandboxGateResult(
        accepted=accepted,
        checks=checks,
        captured_test_output=captured_test_output if accepted else None,
    )
```

(`pipeline/sandbox_gate.py:224-305`)

Checks, in the exact order they run, `N + 3` total where `N = len(wrong_fixes)`
(always 3 today, since `PredictFixCandidate.wrong_fixes` is fixed-length):

1. **`correct_fix_passes_test`** — `fixed_run_a.exit_code == 0`. Runs
   `_concat_snippets(fixed_code, test_code)` through the sandbox TWICE
   (`fixed_run_a`, `fixed_run_b`), but only `run_a`'s exit code gates this
   check; `run_b` exists solely to feed the determinism comparison later.
2. **`buggy_fails_test`** — `buggy_run_a.exit_code != 0 and "AssertionError" in
   buggy_run_a.stderr`. Not just nonzero exit — the string `"AssertionError"`
   must literally appear in stderr. `captured_test_output` (later shown to the
   user as the payload's `test_output`) is set to `buggy_run_a.stderr` **only
   if `ok_buggy` is true**; otherwise `None`.
3. **`distractor_{i}_still_fails_test`** (one per wrong fix, `i` = 0-indexed
   position in the `wrong_fixes` list — NOT the shuffled choice_id, see
   section F) — `run_a.exit_code != 0 and "AssertionError" in run_a.stderr`.
   **Exactly the same condition as `buggy_fails_test`.** This directly
   answers your question: a distractor that crashes with any exception OTHER
   than `AssertionError` (e.g. `TypeError`, `KeyError`, an unguarded
   `IndexError`) does **NOT** count as "still fails" — `"AssertionError" in
   run_a.stderr` is false, so `still_fails` is false, and this check REJECTS
   the whole PTF candidate. The gate's own docstring is explicit about this:
   *"a distractor that fails with anything other than AssertionError is
   broken code, not a plausible fix, and also rejects."* There is no
   "any nonzero exit counts" fallback anywhere in this function.
4. **`deterministic_double_run`** — one combined boolean, accumulated across
   ALL prior runs: `fixed` (`run_a` vs `run_b`), `buggy` (`run_a` vs `run_b`),
   and **every** distractor's `run_a` vs `run_b`, each compared as the full
   3-tuple `(exit_code, stdout, stderr)`. A single nondeterministic distractor
   fails this one check, not a per-distractor determinism check.
5. **`distractors_distinct`** — `len(set(normalized)) == len(normalized) and
   not (set(normalized) & reference)`, where `normalized = [w.strip() for w in
   wrong_fixes]` and `reference = {buggy_code.strip(), fixed_code.strip()}`.
   This is the only "minimality/diff" style check the PTF gate has, and it is
   purely a **textual-equality** check (after `.strip()`), not a line-diff or
   rewrite-cap check like STB's `fix_diff_real_and_minimal` (`sandbox_gate.py:
   82-104, 158-188`). A distractor that differs from `buggy_code`/`fixed_code`
   by even one whitespace-insensitive character passes this check regardless
   of how large or small the edit is. **There is no equivalent of STB's
   diff-derived `verified_bug_lines` / rewrite-size cap for PTF distractors.**

**On STB's B4 claim-check equivalent:** there is none. STB's check 6
(`stb_claim_matches_execution`, `sandbox_gate.py:200-213`) compares the
generator's *claimed* stdout on a divergence input against actual execution.
PTF has no claimed-output field to check against at all — `PredictFixVariant`
carries only `code` and `note` (a rationale string, never validated against
execution). The only thing PTF verifies about a distractor is that it still
raises `AssertionError`; it never checks *what* the distractor's incorrect
behavior actually is against any claim.

`accepted = all(c.passed for c in checks)` — every single check must pass;
there is no partial-credit/flag path (contrast with the semantic gates in
section E, which have a FLAG verdict). One failing distractor anywhere fails
the entire PTF, dropping straight to the D-89 reject-report machinery
(D-89, this session's own fix — see conversation, not in this document's
source citations).

---

## C. THE DERIVATION — `pipeline/predict_the_fix.py`

### What's reused vs. generated

Module docstring states the contract plainly:

```python
"""predict_the_fix derivation (D-80).

Derived from a sandbox-verified spot_the_bug candidate: it reuses that
candidate's (buggy_code, fixed_code, test_code) triple -- already proven by
execution to fail on buggy and pass on fixed -- and asks the generator ONLY for
wrong-fix distractors. Every distractor is then re-executed against the same
test in the sandbox and MUST STILL FAIL; the correct choice is the verified
fixed_code, never a model claim (invariant 1 / D-9). Grading is deterministic
(choice_id), same as trace, so there is zero per-answer LLM cost.

This module owns the derivation logic (generate -> static gate -> sandbox gate
-> assemble the payload/grading/explanation dicts). The DB insert lives in
publish.insert_predict_the_fix, per the module boundary law (only publish.py
touches backend.app).
"""
```

(`pipeline/predict_the_fix.py:1-15`)

**REUSED verbatim from the upstream STB survivor** (never regenerated, never
re-verified against a fresh model claim):
- `buggy_code` — shown to the user in the PTF payload as-is.
- `fixed_code` — becomes the correct choice's text, verbatim.
- `test_code` — sent to the LLM as context and re-executed in the sandbox;
  shown to the user in the payload as `failing_test`.
- `context_note` — copied into the PTF payload unchanged.
- `draft_explanation.summary` / `.principle` — copied into the PTF explanation
  unchanged (see the `explanation` dict below).
- `concepts` — passed through to `insert_predict_the_fix`'s `concepts` arg by
  the caller (`orchestrator.py:990`: `concepts=list(stb_candidate.concepts)`).

**GENERATED by the LLM (one call, `generate_wrong_fixes`):** exactly the 3
`wrong_fixes` entries (`code` + `note` each). Nothing else — the LLM never
sees or restates the correct fix's identity, never proposes a test, never
proposes a context note.

`generate_wrong_fixes`, verbatim:

```python
def generate_wrong_fixes(
    *,
    buggy_code: str,
    fixed_code: str,
    test_code: str,
    concept: str,
    domain: str,
    llm_client: LLMClient,
) -> tuple[PredictFixCandidate | None, str | None]:
    """Ask the generator for 3 wrong-fix distractors. Returns
    (candidate, discard_reason); candidate is None on any parse/abort/schema
    failure (a discard, never a repair -- D-10; the correct choice is already
    verified upstream, so a failed distractor generation just skips deriving a
    predict_the_fix for this STB, it never blocks the STB itself).
    """
    template = load_template("predict_the_fix")
    variables = {
        "python_version": PYTHON_VERSION,
        "concept": concept,
        "domain": domain,
        "buggy_code": buggy_code,
        "fixed_code": fixed_code,
        "test_code": test_code,
    }
    user_prompt = _render(template.user, variables)
    raw = llm_client.complete(system=template.system, user=user_prompt, temperature=_TEMPERATURE)
    parsed = _try_parse_json(raw)
    if parsed is None:
        return None, "json_parse_failed"
    if isinstance(parsed, dict) and parsed.get("abort") is True:
        return None, f"generator_aborted: {parsed.get('reason', 'unspecified')}"
    try:
        return PredictFixCandidate.model_validate(parsed), None
    except Exception as exc:  # noqa: BLE001 -- pydantic ValidationError or bad shape
        return None, f"schema_validation_failed: {exc}"
```

(`pipeline/predict_the_fix.py:86-120`)

`_TEMPERATURE = 0.8` (`pipeline/predict_the_fix.py:33`).

`derive_artifacts`, verbatim (the static gate → sandbox gate → assembly
pipeline):

```python
def derive_artifacts(
    *,
    stb_candidate: STBCandidate,
    wrong_fixes: PredictFixCandidate,
    rng: random.Random,
    line_budget_max: int,
) -> PTFDerivationOutcome:
    """Static-gate every wrong fix, sandbox-prove each STILL FAILS the test,
    then assemble the choice list (correct = verified fixed_code, order
    randomized). Rejects (never repairs) on any gate failure.
    """
    report: dict[str, Any] = {"template_id": "ptf_py_v1"}
    variant_codes = [v.code for v in wrong_fixes.wrong_fixes]

    # Static gate on each shown-to-the-user variant (max line budget only, per
    # D-80; forbidden imports/calls and hint words always run).
    static_violations: list[str] = []
    for code in variant_codes:
        result = static_gate.check(code, line_budget=(None, line_budget_max))
        static_violations.extend(result.violations)
    report["static_gate"] = {"accepted": not static_violations, "violations": static_violations}
    if static_violations:
        return PTFDerivationOutcome(None, "ptf_static_gate", report)

    sandbox = validate_predict_the_fix(
        buggy_code=stb_candidate.buggy_code,
        fixed_code=stb_candidate.fixed_code,
        test_code=stb_candidate.test_code,
        wrong_fixes=variant_codes,
    )
    report["sandbox_gate"] = sandbox.as_report()
    if not sandbox.accepted:
        return PTFDerivationOutcome(None, "ptf_sandbox_gate", report)

    # Assemble choices: the verified fix plus the 3 proven-still-failing
    # distractors, order randomized so the correct one is not always first.
    entries: list[dict[str, Any]] = [
        {"code": stb_candidate.fixed_code, "note": None, "is_correct": True},
    ]
    for variant in wrong_fixes.wrong_fixes:
        entries.append({"code": variant.code, "note": variant.note, "is_correct": False})
    rng.shuffle(entries)

    choices: list[dict[str, str]] = []
    why_wrong: list[dict[str, str]] = []
    correct_choice_id = ""
    for choice_id, entry in zip(_CHOICE_IDS, entries, strict=True):
        choices.append({"id": choice_id, "text": entry["code"]})
        if entry["is_correct"]:
            correct_choice_id = choice_id
        else:
            why_wrong.append({"choice_id": choice_id, "note": entry["note"]})

    test_output = (sandbox.captured_test_output or "").strip()[-_TEST_OUTPUT_TAIL:]

    payload = {
        "code": stb_candidate.buggy_code,
        "context_note": stb_candidate.context_note,
        "question": _QUESTION,
        "failing_test": stb_candidate.test_code,
        "test_output": test_output,
        # answer_mode mirrors the STB/trace payload convention; the client
        # renders a choice list of code diffs.
        "answer_mode": "choose_fix",
        "choices": choices,
    }
    grading = {
        "mode": "deterministic",
        "correct_choice_id": correct_choice_id,
        "artifacts": {
            "fixed_code_hash": hashlib.sha256(
                stb_candidate.fixed_code.encode("utf-8"),
            ).hexdigest(),
            "sandbox_checks": sandbox.as_report(),
        },
    }
    explanation = {
        "summary": stb_candidate.draft_explanation.summary,
        "principle": stb_candidate.draft_explanation.principle,
        "why_wrong": why_wrong,
        "verified": {
            # The correct fix is the execution-proven fixed_code, shown as the
            # winning choice; recorded here for review receipts (D-49 spirit).
            "correct_choice_id": correct_choice_id,
        },
    }
    content_hash = _ptf_content_hash(stb_candidate.buggy_code, variant_codes)

    return PTFDerivationOutcome(
        PTFArtifacts(
            payload=payload,
            grading=grading,
            explanation=explanation,
            content_hash=content_hash,
            correct_choice_id=correct_choice_id,
        ),
        None,
        report,
    )
```

(`pipeline/predict_the_fix.py:123-221`)

Note `_QUESTION = "The test below fails on this code. Which change makes the
test pass?"` and `_CHOICE_IDS = ("a", "b", "c", "d")` and `_TEST_OUTPUT_TAIL =
600` (`pipeline/predict_the_fix.py:34-38`) — the tail-trim applies AFTER
`.strip()`, taking the LAST 600 characters (so a long traceback keeps its
`AssertionError` line, which is always at the end).

The static gate call is `static_gate.check(code, line_budget=(None,
line_budget_max))` — **min is `None`** (no minimum line count enforced on a
distractor), max is the spec's `line_budget_max`. Forbidden imports/calls and
hint-word checks (whatever `static_gate.check` runs generally) apply
unconditionally; only the line-count bound is loosened to max-only.

### The orchestrator call site — what actually triggers a derivation

`derive_artifacts`/`generate_wrong_fixes` are invoked from exactly one place
in the whole codebase, `pipeline/orchestrator.py`'s `_derive_and_publish_ptf`,
called immediately after a **freshly generated, in-memory** STB candidate
just published in the SAME batch run:

```python
async def _derive_and_publish_ptf(
    session: AsyncSession,
    spec: ExerciseSpec,
    stb_candidate: STBCandidate,
    stb_exercise: Any,
    generator_client: LLMClient,
    generator_model: str,
    rng: random.Random,
    report: BatchReport,
) -> None:
    """Derive + publish a predict_the_fix from a just-published STB (D-80).

    One extra generator call (the wrong-fix distractors) plus a sandbox pass
    proving each distractor still fails the test. Every failure mode is a plain
    skip -- the STB is already published and never affected.
    """
    report.counts["ptf_derivation_attempted"] += 1
    wrong_fixes, discard_reason = generate_wrong_fixes(
        buggy_code=stb_candidate.buggy_code,
        fixed_code=stb_candidate.fixed_code,
        test_code=stb_candidate.test_code,
        concept=spec.concept,
        domain=spec.domain,
        llm_client=generator_client,
    )
    if wrong_fixes is None:
        report.counts[f"ptf_generate_discarded:{discard_reason}"] += 1
        return

    ptf = derive_artifacts(
        stb_candidate=stb_candidate,
        wrong_fixes=wrong_fixes,
        rng=rng,
        line_budget_max=spec.line_budget_max,
    )
    if not ptf.survived:
        ...  # (D-89: now writes a reject report; not part of this audit's scope)
        return

    artifacts = ptf.artifacts
    stb_source = stb_exercise.source if isinstance(stb_exercise.source, dict) else {}
    ptf_exercise = await insert_predict_the_fix(
        session,
        concepts=list(stb_candidate.concepts),
        difficulty_authored=spec.difficulty,
        payload=artifacts.payload,
        grading=artifacts.grading,
        explanation=artifacts.explanation,
        content_hash=artifacts.content_hash,
        validation_report=ptf.validation_report,
        generator_model=generator_model,
        derived_from_id=stb_exercise.id,
        derived_from_version=stb_exercise.version,
        stb_template_id=stb_source.get("prompt_template_id"),
    )
    report.counts["ptf_published_in_review"] += 1
    report.counts[f"concept:{spec.concept}:ptf_published"] += 1
    report.ptf_published.append((str(ptf_exercise.id), ptf_exercise.version))
```

(`pipeline/orchestrator.py:943-1004`, elided at the reject branch per this
session's D-89 change, which is out of scope for this audit)

Called from `_publish_survivor` only `if derive_predict_the_fix and
survivor.verified_bug_lines:` (`pipeline/orchestrator.py:821`), i.e. only for
a `has_bug=True` STB survivor, and only within the same process/run that just
generated it — `stb_exercise` is the freshly-`await`ed return value of
`insert_candidate` in the same function, not a row loaded back from the DB.

### `prompts/generator_predict_the_fix_python_v1.md` — verbatim

```
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
```

(`prompts/generator_predict_the_fix_python_v1.md`, full file, 109 lines)

---

## D. THE INGEST BLOCKER — scoping only, NOT implemented

`pipeline/ingest.py` is hardcoded to `spot_the_bug` at three separate,
independent points. None of these were touched.

**1. `_build_spec` hard-rejects any other type:**

```python
def _build_spec(raw: dict[str, Any]) -> ExerciseSpec:
    exercise_type = raw.get("type")
    if exercise_type != "spot_the_bug":
        raise IngestLoadError(
            f"unsupported spec.type {exercise_type!r}: ingest currently only handles spot_the_bug",
        )
```

(`pipeline/ingest.py:91-96`)

It also validates `concept` against `_STB_CONCEPT_SLUGS = frozenset(c.slug for
c in concepts_for_type("spot_the_bug"))` (`pipeline/ingest.py:74, 103-108`) —
a PTF batch's concepts come from the underlying STB anyway (`derive_artifacts`
never samples/validates concepts itself; `concepts_for_type("predict_the_fix")`
is a different taxonomy slice — see `pipeline/taxonomy.py`, not audited here),
so this check would need to accept whichever taxonomy slice applies to
whatever `type` the raw spec declares, not always the STB slice.

**2. `load_batch` hardcodes the candidate schema to `STBCandidate`:**

```python
            spec = _build_spec(raw_spec)
            candidate = STBCandidate.model_validate(raw_candidate)
```

(`pipeline/ingest.py:153-154`)

**3. `IngestItem` itself is typed to `STBCandidate`:**

```python
@dataclasses.dataclass(frozen=True)
class IngestItem:
    spec: ExerciseSpec
    candidate: STBCandidate
```

(`pipeline/ingest.py:85-88`)

**4. The gate call in `ingest_batch` reuses `orchestrator._evaluate_candidate`
verbatim** (`pipeline/ingest.py:49-54` imports it; `pipeline/ingest.py:204-213`
calls it) — and **`_evaluate_candidate` has no branch for a PTF-shaped
candidate at all.** Its only two branches are `isinstance(candidate,
STBCandidate)` (STB path: static_gate → `validate_spot_the_bug` → STB semantic
gates) and the `else` (trace path: static_gate → `validate_trace` → trace
semantic gate) — confirmed by reading the function directly
(`pipeline/orchestrator.py:543-676`; the branch point is
`pipeline/orchestrator.py:579` `if isinstance(candidate, STBCandidate):` /
`pipeline/orchestrator.py:612` `else:`). There is no third branch, and PTF
derivation (`derive_artifacts`/`validate_predict_the_fix`) is never called
from inside `_evaluate_candidate` in the current codebase — it is only ever
called from `_derive_and_publish_ptf`, a completely separate function that
runs strictly AFTER a survivor already cleared `_evaluate_candidate` as an
STB.

**What accepting a hand-authored PTF batch would require (scoping, per D-87 —
reuse existing gate functions verbatim, add no parallel path):**

- A new schema for the full hand-authored PTF item: the STB triple fields
  (`buggy_code`, `fixed_code`, `test_code`, `context_note`, an explanation
  summary/principle) PLUS a `wrong_fixes` list shaped like
  `PredictFixCandidate.wrong_fixes` (3 `{code, note}` entries) — because
  today's `PredictFixCandidate` assumes the triple already exists as an
  in-memory `STBCandidate` from the SAME batch run; a hand-authored PTF has no
  such object unless the batch also constructs one.
- `_build_spec` would need a second branch for `type == "predict_the_fix"`
  (or a caller-supplied concept-taxonomy lookup keyed by type instead of the
  hardcoded `_STB_CONCEPT_SLUGS`).
- The gate call should NOT go through `_evaluate_candidate` (it has no PTF
  branch, and adding one there would entangle STB/trace's static+sandbox+
  semantic chain with PTF's different chain — static_gate on distractors only,
  no semantic gates at all, see section E). The correct reuse target is
  `predict_the_fix.derive_artifacts` directly — it already takes a
  `stb_candidate`-shaped object and a `PredictFixCandidate`-shaped
  `wrong_fixes` object and runs static_gate + `validate_predict_the_fix`
  verbatim, with **no LLM call** needed for a hand-authored batch (the
  distractors are already written — `generate_wrong_fixes` would be skipped
  entirely, not reused, since there's no generation step for hand-authored
  content).
- `insert_predict_the_fix` requires `derived_from_id`/`derived_from_version`
  (`pipeline/publish.py:232-233`) pointing at a real, already-inserted STB
  `Exercise` row. A hand-authored PTF batch would need to either (a) also
  ingest/publish its own STB half through the EXISTING STB ingest path first,
  then feed that just-inserted STB exercise's `id`/`version` into the PTF
  insert (mirroring `_derive_and_publish_ptf`'s `stb_exercise` argument
  exactly), or (b) if the PTF is meant to stand alone with no published STB
  counterpart, `derived_from_id`/`version` would need to become optional — a
  contract change to `insert_predict_the_fix`, not just ingest.py.
- A new reject-report stage tag alongside the existing `"load"` stage
  (`pipeline/ingest.py:157-166`), since a hand-authored PTF's own gate
  (`derive_artifacts`) already produces `"ptf_static_gate"`/`"ptf_sandbox_gate"`
  as its `reject_stage` (section C) — those should stay as-is and reuse
  `write_reject_report` exactly as D-89 just wired it for the orchestrator
  path, not get a third naming scheme.

None of the above was implemented. This is scope only, per your instruction.

---

## E. SEMANTIC GATES

**PTF candidates go through NO semantic gates at all** — a different
(empty) set from STB and trace, not a variant of their set.

`prompts/gates_v1.md`'s own header states its scope precisely:

```
# prompt_template_ids: gate_solver_v1, gate_defect_audit_v1, gate_reasons_v1
# Run at temperature 0, on a DIFFERENT model/family than the generator.
# All three receive ONLY what they need; none ever sees the generator's answers
# except where explicitly stated. Order: defect_audit -> solver -> reasons.
```

(`prompts/gates_v1.md:1-4`)

The file documents exactly three gates, each explicitly scoped:

```
## GATE 1: gate_defect_audit_v1  (spot_the_bug only)
...
## GATE 2: gate_solver_v1  (both types)
...
## GATE 3: gate_reasons_v1  (spot_the_bug only)
```

(`prompts/gates_v1.md:7, 64, 105`)

"both types" (GATE 2's scope note) means spot_the_bug and trace — the two
types that existed when this doc was written; there is no fourth
`predict_the_fix`-scoped gate anywhere in the file, and no mention of
`predict_the_fix` at all in `prompts/gates_v1.md`. This matches the code
exactly: `orchestrator._derive_and_publish_ptf` (section C) calls only
`generate_wrong_fixes` (an LLM call, but for CONTENT generation, not
judging/gating) and `derive_artifacts` (static_gate + sandbox gate). Neither
`_run_stb_semantic_gates` nor `_run_trace_semantic_gates`
(`pipeline/orchestrator.py:355-458`) — nor any PTF-specific equivalent — is
ever invoked for a PTF candidate. `derive_artifacts` accepts no `gate_client`
parameter at all (`pipeline/predict_the_fix.py:123-129` signature: `stb_
candidate`, `wrong_fixes`, `rng`, `line_budget_max` — no LLM client).

The module docstring's framing ("Grading is deterministic (choice_id), same
as trace, so there is zero per-answer LLM cost", `pipeline/predict_the_fix.py:
8-9`) is the design intent behind this: PTF's trust guarantee is 100%
execution (sandbox), 0% LLM judgment — even less LLM involvement than trace,
which still runs one solver pass (`gate_solver_v1`).

---

## F. THE REAL SHAPE

### `pipeline/publish.py` — `insert_predict_the_fix`

```python
async def insert_predict_the_fix(
    session: AsyncSession,
    *,
    concepts: list[str],
    difficulty_authored: int,
    payload: dict[str, Any],
    grading: dict[str, Any],
    explanation: dict[str, Any],
    content_hash: str,
    validation_report: dict[str, Any],
    generator_model: str,
    derived_from_id: uuid.UUID,
    derived_from_version: int,
    stb_template_id: str | None,
) -> Exercise:
    """Insert a predict_the_fix exercise derived from a verified spot_the_bug
    (D-80). Deterministic grading; the correct choice is the execution-proven
    fixed_code (already baked into `grading.correct_choice_id`), never a model
    claim. `source.derived_from` records the parent STB so a reviewer can trace
    both back to the same verified artifacts.
    """
    exercise_id = uuid.uuid4()
    version = 1
    report_path = write_validation_report(validation_report, exercise_id, version)

    source: dict[str, Any] = {
        "origin": "llm",
        "model": generator_model,
        "prompt_template_id": "ptf_py_v1",
        "stb_prompt_template_id": stb_template_id,
        "content_hash": content_hash,
        "taxonomy_version": taxonomy.TAXONOMY_VERSION,
        "derived_from": {"id": str(derived_from_id), "version": derived_from_version},
    }

    exercise = Exercise(
        id=exercise_id,
        version=version,
        language="python",
        type="predict_the_fix",
        grading_mode="deterministic",
        difficulty_authored=difficulty_authored,
        concepts=concepts,
        tags=[],
        status="in_review",
        source=source,
        payload=payload,
        grading=grading,
        explanation=explanation,
        validation_report_url=report_path,
        human_reviewed=False,
    )
    session.add(exercise)
    await session.flush()
    return exercise
```

(`pipeline/publish.py:221-275`)

`payload`/`grading`/`explanation` are passed straight through from
`PTFArtifacts` (`derive_artifacts`'s return value, section C) — `publish.py`
does not reshape them for PTF the way it does for STB/trace (compare
`_stb_payload`/`_stb_grading`/`_trace_payload`/`_trace_grading`,
`pipeline/publish.py:83-140`, which exist only for those two types). `source`
is hardcoded to `"origin": "llm"` — there is no `origin` parameter on this
function (unlike `insert_candidate`, which takes `origin: str = "llm"` for the
D-87 hand-authored path). **A hand-authored PTF batch would need this
function to accept an `origin` override too**, or every hand-authored PTF
would be mislabeled `"llm"` in `source.origin` — noted for section D's scope,
not implemented.

### One published `predict_the_fix` row, verbatim from the live DB

```
$ docker compose exec postgres psql -U codereader -d codereader -c \
    "SELECT payload, grading FROM exercises WHERE type='predict_the_fix' LIMIT 1;"
```

**payload:**

```json
{
  "code": "def select_top_scores(scores, limit):\n    ordered = sorted(scores, reverse=True)\n    selected = []\n    for index in range(len(ordered)):\n        if index > limit:\n            break\n        selected.append(ordered[index])\n    return selected\n",
  "choices": [
    {"id": "a", "text": "def select_top_scores(scores, limit):\n    ordered = sorted(scores, reverse=True)\n    selected = []\n    count = 0\n    for score in ordered:\n        if count > limit:\n            break\n        selected.append(score)\n        count += 1\n    return selected\n"},
    {"id": "b", "text": "def select_top_scores(scores, limit):\n    ordered = sorted(scores, reverse=True)\n    selected = []\n    for index in range(limit + 1):\n        if index >= len(ordered):\n            break\n        selected.append(ordered[index])\n    return selected\n"},
    {"id": "c", "text": "def select_top_scores(scores, limit):\n    ordered = sorted(scores, reverse=True)\n    selected = ordered[:limit+1]\n    return selected\n"},
    {"id": "d", "text": "def select_top_scores(scores, limit):\n    ordered = sorted(scores, reverse=True)\n    selected = []\n    for index in range(len(ordered)):\n        if index >= limit:\n            break\n        selected.append(ordered[index])\n    return selected\n"}
  ],
  "question": "The test below fails on this code. Which change makes the test pass?",
  "answer_mode": "choose_fix",
  "test_output": "Traceback (most recent call last):\n  File \"<stdin>\", line 11, in <module>\nAssertionError: the limit caps how many scores are selected",
  "context_note": "Selects the leaderboard entries shown on the results page.",
  "failing_test": "result = select_top_scores([10, 50, 30, 20, 40], 2)\nprint(repr(result))\nassert result == [50, 40], \"the limit caps how many scores are selected\"\n"
}
```

**grading:**

```json
{
  "mode": "deterministic",
  "artifacts": {
    "sandbox_checks": {
      "checks": [
        {"name": "correct_fix_passes_test", "detail": "", "passed": true},
        {"name": "buggy_fails_test", "detail": "Traceback (most recent call last):\n  File \"<stdin>\", line 11, in <module>\nAssertionError: the limit caps how many scores are selected\n", "passed": true},
        {"name": "distractor_0_still_fails_test", "detail": "exit=1 Traceback (most recent call last):\n  File \"<stdin>\", line 11, in <module>\nAssertionError: the limit caps how many scores are selected\n", "passed": true},
        {"name": "distractor_1_still_fails_test", "detail": "exit=1 Traceback (most recent call last):\n  File \"<stdin>\", line 13, in <module>\nAssertionError: the limit caps how many scores are selected\n", "passed": true},
        {"name": "distractor_2_still_fails_test", "detail": "exit=1 Traceback (most recent call last):\n  File \"<stdin>\", line 7, in <module>\nAssertionError: the limit caps how many scores are selected\n", "passed": true},
        {"name": "deterministic_double_run", "detail": "", "passed": true},
        {"name": "distractors_distinct", "detail": "each wrong fix must differ from buggy_code, fixed_code, and the others", "passed": true}
      ],
      "accepted": true,
      "captured_stdout": null,
      "verified_bug_lines": null,
      "captured_test_output": "Traceback (most recent call last):\n  File \"<stdin>\", line 11, in <module>\nAssertionError: the limit caps how many scores are selected\n",
      "bug_lines_claim_mismatch": false
    },
    "fixed_code_hash": "f961ab18fd3ecd8482fc01f913c6e5f4d1b277c601312e401cf9068f8a45d489"
  },
  "correct_choice_id": "d"
}
```

Observations that matter for hand-authoring:

- `payload.choices` carry only `{"id", "text"}` — **the correct answer is
  never marked in the payload.** `grading.correct_choice_id` (here `"d"`) is
  the only place the key lives, and `grading` is never serialized to the
  client pre-attempt per CLAUDE.md invariant 2.
- `payload` has **no `wrong_fix.note` fields** — those live only in
  `explanation.why_wrong` (not shown in this query, but constructed in
  `derive_artifacts`, section C) and are revealed post-attempt only.
- `grading.artifacts.fixed_code_hash` is a bare sha256 of `fixed_code` — the
  actual `fixed_code` text is **not stored anywhere in this row**. It only
  ever exists, verbatim, as one of the 4 `payload.choices[*].text` entries
  (here, `choices[3]`, `id: "d"`, matching `correct_choice_id: "d"`) — i.e.
  the only way to recover `fixed_code` from a published PTF row is to read
  off whichever choice's `id` matches `grading.correct_choice_id`.
- Distractor indices in `grading.artifacts.sandbox_checks.checks` (`distractor_
  0`, `distractor_1`, `distractor_2`) are in the ORIGINAL, pre-shuffle
  `wrong_fixes` list order — they do NOT correspond 1:1 with `payload.choices`
  order, which was shuffled by `rng.shuffle(entries)` in `derive_artifacts`
  (section C). Cross-referencing a specific distractor's sandbox detail back
  to its shown `choice_id` requires matching by `code` text, not by index.
