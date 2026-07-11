"""Dry-run: validate one spot_the_bug candidate using the exact sandbox-gate
rules from generator_spot_the_bug_python_v2.md pipeline notes."""
import difflib, io, json, contextlib, math

candidate = {
    "buggy_code": (
        "def apply_discount(prices, discount_pct):\n"
        "    updated = prices\n"
        "    for sku in updated:\n"
        "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
        "    return updated\n"
    ),
    "fixed_code": (
        "def apply_discount(prices, discount_pct):\n"
        "    updated = dict(prices)\n"
        "    for sku in updated:\n"
        "        updated[sku] = round(updated[sku] * (1 - discount_pct / 100), 2)\n"
        "    return updated\n"
    ),
    "bug_lines": [2],
    "test_code": (
        "prices = {'A1': 100.0, 'B2': 50.0}\n"
        "result = apply_discount(prices, 10)\n"
        "assert result == {'A1': 90.0, 'B2': 45.0}\n"
        "assert prices == {'A1': 100.0, 'B2': 50.0}, 'input dict was mutated'\n"
    ),
    "has_bug": True,
}

# D-49 rewrite cap: a fix changing more original lines than max(5, 20% of the
# file) is a rewrite, not a minimal fix.
REWRITE_CAP_MIN_LINES = 5
REWRITE_CAP_FRACTION = 0.2

def concat(code, test_code):
    """Join code + test, inserting the newline the generator may have dropped
    (D-50). Can only repair the syntax the raw concatenation would break;
    never a false accept."""
    if code.endswith("\n"):
        return code + test_code
    return code + "\n" + test_code

def run(code):
    """Execute code, return (passed, output). Stand-in for the sandbox."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(code, "<candidate>", "exec"), {})
        return True, buf.getvalue()
    except AssertionError as e:
        return False, f"AssertionError: {e}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"  # non-assert error = broken candidate

checks = {}

# 1. buggy + test must FAIL with AssertionError
p1, o1 = run(concat(candidate["buggy_code"], candidate["test_code"]))
checks["buggy_fails_test"] = (p1 is False, o1)

# 2. fixed + test must PASS
p2, o2 = run(concat(candidate["fixed_code"], candidate["test_code"]))
checks["fixed_passes_test"] = (p2 is True, o2)

# 3. buggy alone must not raise (happy path)
p3, o3 = run(candidate["buggy_code"])
checks["buggy_runs_clean"] = (p3 is True, o3)

# 4. determinism: run everything twice, outputs identical
det = all(run(concat(candidate["buggy_code"], candidate["test_code"]))[1] == o1 and
          run(concat(candidate["fixed_code"], candidate["test_code"]))[1] == o2
          for _ in range(1))
checks["deterministic_double_run"] = (det, "")

# 5. has_bug=False: fixed_code must be byte-identical to buggy_code and
#    bug_lines == []. has_bug=True (D-49): the answer key is DERIVED from a
#    real (SequenceMatcher) diff -- the buggy_code lines the fix replaces or
#    deletes become verified_bug_lines. The generator's declared bug_lines
#    are compared and logged as a quality metric, never a reject by
#    themselves. Rejected only when the diff shows no real edit (pure
#    insertion) or a rewrite-sized change (over the minimal-fix cap).
buggy_lines = candidate["buggy_code"].splitlines()
fixed_lines = candidate["fixed_code"].splitlines()
matcher = difflib.SequenceMatcher(a=buggy_lines, b=fixed_lines, autojunk=False)
changed = []
for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
    if tag in ("replace", "delete"):
        changed.extend(range(i1 + 1, i2 + 1))
verified_bug_lines = None
claim_mismatch = False
if candidate["has_bug"]:
    claim_mismatch = changed != candidate["bug_lines"]
    cap = max(REWRITE_CAP_MIN_LINES, math.ceil(len(buggy_lines) * REWRITE_CAP_FRACTION))
    if not changed:
        ok5, detail = False, "fix replaces or deletes no existing line (pure insertion)"
    elif len(changed) > cap:
        ok5, detail = False, f"fix changes {len(changed)} original lines, over the cap of {cap}"
    else:
        ok5 = True
        verified_bug_lines = changed
        detail = f"verified bug_lines {changed} (diff-derived); generator claimed {candidate['bug_lines']}"
else:
    ok5 = candidate["fixed_code"] == candidate["buggy_code"] and candidate["bug_lines"] == []
    verified_bug_lines = [] if ok5 else None
    detail = f"diff says {changed}, candidate says {candidate['bug_lines']}"
checks["fix_diff_real_and_minimal"] = (ok5, detail)

verdict = all(ok for ok, _ in checks.values())
for name, (ok, detail) in checks.items():
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip())
if claim_mismatch:
    print("NOTE  bug_lines claim mismatch (logged, not a reject)")
print("\nCANDIDATE VERDICT:", "ACCEPTED" if verdict else "REJECTED")
if verdict and candidate["has_bug"]:
    print("VERIFIED BUG LINES:", verified_bug_lines)
