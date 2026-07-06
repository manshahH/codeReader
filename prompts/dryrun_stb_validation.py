"""Dry-run: validate one spot_the_bug candidate using the exact sandbox-gate
rules from generator_spot_the_bug_python_v1.md pipeline notes."""
import difflib, io, json, contextlib

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
p1, o1 = run(candidate["buggy_code"] + candidate["test_code"])
checks["buggy_fails_test"] = (p1 is False, o1)

# 2. fixed + test must PASS
p2, o2 = run(candidate["fixed_code"] + candidate["test_code"])
checks["fixed_passes_test"] = (p2 is True, o2)

# 3. buggy alone must not raise (happy path)
p3, o3 = run(candidate["buggy_code"])
checks["buggy_runs_clean"] = (p3 is True, o3)

# 4. determinism: run everything twice, outputs identical
det = all(run(candidate["buggy_code"] + candidate["test_code"])[1] == o1 and
          run(candidate["fixed_code"] + candidate["test_code"])[1] == o2
          for _ in range(1))
checks["deterministic_double_run"] = (det, "")

# 5. diff(buggy, fixed) changed lines must equal bug_lines exactly
buggy_lines = candidate["buggy_code"].splitlines()
fixed_lines = candidate["fixed_code"].splitlines()
changed = []
for i, (a, b) in enumerate(zip(buggy_lines, fixed_lines), start=1):
    if a != b:
        changed.append(i)
changed += list(range(min(len(buggy_lines), len(fixed_lines)) + 1,
                      max(len(buggy_lines), len(fixed_lines)) + 1))
checks["bug_lines_match_diff"] = (changed == candidate["bug_lines"],
                                  f"diff says {changed}, candidate says {candidate['bug_lines']}")

verdict = all(ok for ok, _ in checks.values())
for name, (ok, detail) in checks.items():
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip())
print("\nCANDIDATE VERDICT:", "ACCEPTED" if verdict else "REJECTED")
