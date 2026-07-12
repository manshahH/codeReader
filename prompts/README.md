# Content Generation Prompts : v1 (Python)

How these files fit into the pipeline:

```
SPEC SAMPLER -> [generator_*.md] -> STATIC GATE -> SANDBOX GATE -> [gates.md] -> DEDUP -> EXPLAIN -> REVIEW
```

## Files

| File | Role | Model | Temp |
|---|---|---|---|
| `generator_spot_the_bug_python_v5.md` | produces STB candidates | strong model (Sonnet-class or better), or GENERATOR_MODEL_STB override (D-80) | 0.8 |
| `generator_predict_the_fix_python_v1.md` | produces wrong-fix distractors for a verified STB (D-80) | strong model | 0.8 |
| `generator_trace_python_v2.md` | produces Trace candidates | strong model | 0.8 |
| `repair_spot_the_bug_python_v1.md` | targeted repair of a REPAIRABLE STB rejection (D-83) | same generator | 0.8 |
| `repair_trace_python_v1.md` | targeted repair of a REPAIRABLE trace rejection (D-83) | same generator | 0.8 |
| `gates_v1.md` | adversarial checks post-sandbox | DIFFERENT model/family than generator | 0.0 |

(`generator_spot_the_bug_python_v1.md`, `_v2.md`, `_v3.md`, and `_v4.md` are
retired but kept for traceability of already-generated candidates; D-46 edited v1
in place, so v1 on disk reflects its final, not original, state -- noted in D-53.
v3 added the single divergence-boundary worked example (D-80) but did not move the
non-discriminating-test reject rate. v4 (D-82) decomposes generation into
correct-code-first -> plant one bug -> DERIVE the divergence as required fields ->
a test that prints repr(result) and asserts on the divergence input, adds three
structurally different worked examples, and is backed by the free B3 schema check
and the B4 execution claim-check. v5 (D-86) is v4 with its content byte-identical
but the varying `## Specification` block relocated to the END so the static prefix
is prompt-cacheable; `generator_trace_python_v1.md` is likewise retired for its
cache-optimized v2. The `repair_*` templates (D-83) are handed a REPAIRABLE
rejection's original candidate + failed check + evidence and asked to change only
what the failure requires; the repaired candidate re-runs the FULL gate chain.)

`generator_predict_the_fix_python_v1.md` is NOT sampled from a spec: it is
handed a verified STB's (buggy, fixed, test) triple and asked only for wrong-fix
distractors. Its correct answer is the execution-proven fixed_code, and every
distractor is re-executed and must STILL FAIL the test (D-80).

Generator temperature is high for variety; gate temperature is 0 because gates are judges, not writers.

## The contract every template obeys

1. **Output is a single JSON object.** No markdown fences, no prose before or after. Pipeline parses with a strict Pydantic schema; anything unparseable is rejected and retried once, then dropped.
2. **The generator's claimed answers are NEVER trusted.** For trace, `expected_stdout` is discarded and recaptured by sandbox execution. For STB, the twin-snippet invariant (test fails on buggy, passes on fixed, both by execution) is the only ground truth. Generator claims exist only for sanity-diffing: if execution disagrees with the claim, that's a strong reject signal worth logging.
3. **Line numbers are 1-indexed against the code exactly as emitted.** The sandbox gate joins code and test with a newline itself if the code's trailing newline is missing (D-50), and DERIVES the published `bug_lines` by diffing buggy vs fixed (D-49) -- the generator's declared `bug_lines` are compared against the diff and logged as a template quality metric, never trusted as the key and never a reject by themselves.
4. **Determinism rules are absolute** (listed in each template). The sandbox runs everything twice and rejects on any output difference, but the generator must not rely on that safety net.
5. **stdout comparison rule** (trace): captured stdout is compared after exactly one normalization, stripping the single trailing newline if present. Everything else is byte-exact. Templates instruct the generator to avoid outputs that are fragile under this rule (raw float repr, set iteration, dict ordering games).

## Template variables (filled by the spec sampler)

| Variable | Example | Notes |
|---|---|---|
| `{{python_version}}` | `3.12` | matches the sandbox image, always |
| `{{concept}}` | `off-by-one` | ONE concept from the taxonomy per exercise |
| `{{difficulty}}` | `4` | 1..10, operationalized inside each template |
| `{{domain}}` | `inventory service` | realism flavor; sampler rotates ~30 domains |
| `{{line_budget_min}}` / `{{line_budget_max}}` | `20` / `60` | scaled with difficulty |
| `{{has_bug}}` | `true` | STB only; sampler sets `false` ~15% of the time |
| `{{avoid_patterns}}` | `["mutable default argument", ...]` | last N bug mechanisms shipped for this concept, to force variety |

## Retry policy

Per candidate: 1 generation call. On a gate rejection the orchestrator now does one of two things (D-83, superseding the original discard-and-regenerate-only rule of D-10):

- **REPAIRABLE rejection** (a mechanical static violation; a non-discriminating test / mispredicted result / non-self-consistent fix in the sandbox): feed the candidate BACK to the generator with the failed check and its concrete evidence, via `repair_*`, and ask for a targeted fix. The repaired candidate re-runs the FULL gate chain, no exemptions -- a repair is not trusted. At most 2 repairs per candidate, never the same check twice.
- **FUNDAMENTAL rejection** (a genuine second defect, an unsolvable/ambiguous exercise, a `partially_defensible` distractor, a duplicate): the idea is bad; discard and generate fresh. Repairing it is asking the model to rescue a bad idea.

Both fresh generations and repairs draw from one budget of `MAX_ATTEMPTS_PER_SPEC` total generation calls per spec (then the spec is flagged/exhausted). Where budget allows, best-of-N (D-84) collects more than one survivor and publishes the highest-scoring. The one JSON exception is unchanged: a parse failure gets a single "output valid JSON only" retry because nothing semantic is wrong yet.

## Versioning

Template file name is the `prompt_template_id` stored in `exercises.source`. Any edit to a template, however small, bumps the version and creates a new file. This is what lets you trace a bad batch of exercises back to the exact prompt that made them.

One `prompt_template_id` value is not a file: `handauthored_stb_v1` (D-87, `pipeline/ingest.py`) tags a candidate a human wrote directly, with no generator template and no generation call in the loop. It still goes through the same static/sandbox/semantic/dedup gate chain as every template above, on the OpenAI gate path (D-14) since the author is Claude. `source.origin="handauthored_claude"` is the field that actually distinguishes it; the fixed `prompt_template_id` is a load-time-enforced tag, not free text.
