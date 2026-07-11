# Content Generation Prompts : v1 (Python)

How these files fit into the pipeline:

```
SPEC SAMPLER -> [generator_*.md] -> STATIC GATE -> SANDBOX GATE -> [gates.md] -> DEDUP -> EXPLAIN -> REVIEW
```

## Files

| File | Role | Model | Temp |
|---|---|---|---|
| `generator_spot_the_bug_python_v2.md` | produces STB candidates | strong model (Sonnet-class or better) | 0.8 |
| `generator_trace_python_v1.md` | produces Trace candidates | strong model | 0.8 |
| `gates_v1.md` | adversarial checks post-sandbox | DIFFERENT model/family than generator | 0.0 |

(`generator_spot_the_bug_python_v1.md` is retired but kept for traceability of
already-generated candidates; D-46 edited it in place, so v1 on disk reflects
its final, not original, state -- noted in D-53.)

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

Per candidate: 1 generation call. If any gate rejects, do NOT ask the model to "fix" the candidate; discard and generate fresh from the same spec (max 3 specs attempts, then flag the spec). Repaired candidates inherit subtle inconsistencies; fresh ones don't. The one exception: JSON parse failure gets a single "output valid JSON only" retry because nothing semantic is wrong yet.

## Versioning

Template file name is the `prompt_template_id` stored in `exercises.source`. Any edit to a template, however small, bumps the version and creates a new file. This is what lets you trace a bad batch of exercises back to the exact prompt that made them.
