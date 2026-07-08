"""Sandbox validation gate.

Ports the five invariants from prompts/dryrun_stb_validation.py exactly, using
real Docker execution (pipeline.sandbox.runner) instead of in-process exec --
sandbox code is hostile (invariant #7 in CLAUDE.md), so it is never exec()'d on
the pipeline host. Adds the trace rules from the pipeline notes at the bottom
of prompts/generator_trace_python_v1.md: capture stdout, reject on claim
mismatch (D-11), assert distinct from every distractor, and hand back the
captured output so the caller can replace the correct choice's text with it.
"""

from __future__ import annotations

import dataclasses

from pipeline.sandbox.runner import run_python
from pipeline.schemas import STBCandidate, TraceCandidate


@dataclasses.dataclass(frozen=True)
class GateCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclasses.dataclass(frozen=True)
class SandboxGateResult:
    accepted: bool
    checks: list[GateCheck]
    captured_stdout: str | None = None  # trace only: the verified real output

    def as_report(self) -> dict:
        return {
            "accepted": self.accepted,
            "checks": [dataclasses.asdict(c) for c in self.checks],
            "captured_stdout": self.captured_stdout,
        }


def _normalize_stdout(stdout: str) -> str:
    if stdout.endswith("\n"):
        return stdout[:-1]
    return stdout


def _diff_changed_lines(buggy_code: str, fixed_code: str) -> list[int]:
    buggy_lines = buggy_code.splitlines()
    fixed_lines = fixed_code.splitlines()
    changed = [i for i, (a, b) in enumerate(zip(buggy_lines, fixed_lines), start=1) if a != b]
    changed += list(
        range(
            min(len(buggy_lines), len(fixed_lines)) + 1,
            max(len(buggy_lines), len(fixed_lines)) + 1,
        ),
    )
    return changed


def validate_spot_the_bug(candidate: STBCandidate, *, has_bug: bool) -> SandboxGateResult:
    checks: list[GateCheck] = []

    buggy_plus_test = candidate.buggy_code + candidate.test_code
    fixed_plus_test = candidate.fixed_code + candidate.test_code

    # 1. buggy+test FAILS with AssertionError if has_bug, else PASSES.
    run1a = run_python(buggy_plus_test)
    run1b = run_python(buggy_plus_test)
    if has_bug:
        ok1 = run1a.exit_code != 0 and "AssertionError" in run1a.stderr
        checks.append(GateCheck("buggy_fails_test", ok1, run1a.stderr[-500:]))
    else:
        ok1 = run1a.exit_code == 0
        checks.append(GateCheck("buggy_passes_test_when_no_bug", ok1, run1a.stderr[-500:]))

    # 2. fixed+test always PASSES.
    run2a = run_python(fixed_plus_test)
    run2b = run_python(fixed_plus_test)
    ok2 = run2a.exit_code == 0
    checks.append(GateCheck("fixed_passes_test", ok2, run2a.stderr[-500:]))

    # 3. buggy alone must not raise (happy path).
    run3a = run_python(candidate.buggy_code)
    run3b = run_python(candidate.buggy_code)
    ok3 = run3a.exit_code == 0
    checks.append(GateCheck("buggy_runs_clean", ok3, run3a.stderr[-500:]))

    # 4. determinism: every run above, run twice, identical (exit, stdout, stderr).
    det = (
        (run1a.exit_code, run1a.stdout, run1a.stderr)
        == (run1b.exit_code, run1b.stdout, run1b.stderr)
        and (run2a.exit_code, run2a.stdout, run2a.stderr)
        == (run2b.exit_code, run2b.stdout, run2b.stderr)
        and (run3a.exit_code, run3a.stdout, run3a.stderr)
        == (run3b.exit_code, run3b.stdout, run3b.stderr)
    )
    checks.append(GateCheck("deterministic_double_run", det))

    # 5. diff(buggy, fixed) changed lines must equal bug_lines exactly.
    changed = _diff_changed_lines(candidate.buggy_code, candidate.fixed_code)
    expected_bug_lines = candidate.bug_lines if has_bug else []
    ok5 = changed == expected_bug_lines
    checks.append(
        GateCheck(
            "bug_lines_match_diff",
            ok5,
            f"diff says {changed}, candidate says {candidate.bug_lines}",
        ),
    )

    accepted = all(c.passed for c in checks)
    return SandboxGateResult(accepted=accepted, checks=checks)


def validate_trace(candidate: TraceCandidate) -> SandboxGateResult:
    checks: list[GateCheck] = []

    run_a = run_python(candidate.code)
    run_b = run_python(candidate.code)

    ok_runs_clean = run_a.exit_code == 0
    checks.append(GateCheck("code_runs_clean", ok_runs_clean, run_a.stderr[-500:]))

    det = (run_a.exit_code, run_a.stdout, run_a.stderr) == (
        run_b.exit_code,
        run_b.stdout,
        run_b.stderr,
    )
    checks.append(GateCheck("deterministic_double_run", det))

    captured = _normalize_stdout(run_a.stdout)
    expected = _normalize_stdout(candidate.expected_stdout)
    claim_matches = captured == expected
    checks.append(
        GateCheck(
            "captured_output_matches_claim",
            claim_matches,
            f"captured={captured!r} expected_stdout={expected!r}",
        ),
    )

    distractor_texts = [c.text for c in candidate.choices if c.id != candidate.correct_choice_id]
    distinct_from_distractors = captured not in distractor_texts
    checks.append(
        GateCheck("captured_output_distinct_from_distractors", distinct_from_distractors),
    )

    accepted = all(c.passed for c in checks)
    return SandboxGateResult(
        accepted=accepted,
        checks=checks,
        captured_stdout=captured if accepted else None,
    )
