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
import difflib
import math

from pipeline.sandbox.runner import run_python
from pipeline.schemas import STBCandidate, TraceCandidate

# D-49: a fix that replaces/deletes more original lines than this is a rewrite,
# not a minimal fix -- a smeared diff makes every changed line a "correct"
# answer, which is no answer key at all. Cap: 5 lines or 20% of the file,
# whichever is larger.
_REWRITE_CAP_MIN_LINES = 5
_REWRITE_CAP_FRACTION = 0.2


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
    # spot_the_bug only: the diff-derived answer key (D-49). Set on accepted
    # results; the generator's claimed bug_lines never become the key.
    verified_bug_lines: list[int] | None = None
    # spot_the_bug only: the generator's claim disagreed with the diff. A
    # template-quality metric (D-11 style), never a reject by itself.
    bug_lines_claim_mismatch: bool = False

    def as_report(self) -> dict:
        return {
            "accepted": self.accepted,
            "checks": [dataclasses.asdict(c) for c in self.checks],
            "captured_stdout": self.captured_stdout,
            "verified_bug_lines": self.verified_bug_lines,
            "bug_lines_claim_mismatch": self.bug_lines_claim_mismatch,
        }


def _normalize_stdout(stdout: str) -> str:
    if stdout.endswith("\n"):
        return stdout[:-1]
    return stdout


def _concat_snippets(code: str, test_code: str) -> str:
    """Join exercise code and test code into one script, inserting the newline
    the generator may have dropped (D-50). A raw concatenation glues the last
    code line to the first test line when the trailing newline is missing --
    SyntaxError, and a false reject of a perfectly good candidate. Inserting
    the separator is deterministic and can only ever repair syntax the
    concatenation itself would have broken, never change what either snippet
    does, so it cannot create a false accept.
    """
    if code.endswith("\n"):
        return code + test_code
    return code + "\n" + test_code


def _diff_changed_lines(buggy_code: str, fixed_code: str) -> list[int]:
    """1-indexed buggy_code line numbers the fix replaces or deletes.

    A real (SequenceMatcher) diff, not a positional zip: a fix that only
    INSERTS new lines (a new import, a new guard, wrapping existing lines in
    a `with` block) touches zero original line numbers by itself, so it never
    cascades into flagging every line after the insertion. Only lines that
    are actually replaced or removed from buggy_code count -- an insertion
    can accompany a real change but can never substitute for one, since the
    line(s) the fix is supposed to change must still show up here.
    autojunk=False: its "common lines are junk" heuristic is a speed hack for
    large files (200+ lines) that can misclassify frequent short lines (e.g.
    blank lines, `return updated`) in code this size; never worth the risk on
    the trust gate.
    """
    buggy_lines = buggy_code.splitlines()
    fixed_lines = fixed_code.splitlines()
    matcher = difflib.SequenceMatcher(a=buggy_lines, b=fixed_lines, autojunk=False)
    changed: list[int] = []
    for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            changed.extend(range(i1 + 1, i2 + 1))
    return changed


def validate_spot_the_bug(candidate: STBCandidate, *, has_bug: bool) -> SandboxGateResult:
    checks: list[GateCheck] = []

    buggy_plus_test = _concat_snippets(candidate.buggy_code, candidate.test_code)
    fixed_plus_test = _concat_snippets(candidate.fixed_code, candidate.test_code)

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

    # 5. has_bug=False: fixed_code must be byte-identical to buggy_code and
    #    bug_lines == [] -- there is nothing to fix, so nothing may differ.
    #    has_bug=True (D-49): the answer key is DERIVED from the diff -- the
    #    buggy_code lines the fix replaces or deletes, proven by the same
    #    twin-snippet execution as checks 1-2, become verified_bug_lines.
    #    The generator's declared bug_lines are compared and logged as a
    #    template-quality metric (D-11 style) but never gate acceptance: a
    #    model that mis-transcribed a line number did not write a worse
    #    exercise, and the derived key is execution-anchored either way.
    #    Rejected here only when the diff shows no real edit (pure insertion:
    #    nothing for the exercise to point at, indistinguishable from
    #    has_bug=false) or a rewrite-sized change (not a minimal fix).
    changed = _diff_changed_lines(candidate.buggy_code, candidate.fixed_code)
    claim_mismatch = False
    verified_bug_lines: list[int] | None = None
    if has_bug:
        claim_mismatch = changed != candidate.bug_lines
        line_count = len(candidate.buggy_code.splitlines())
        cap = max(_REWRITE_CAP_MIN_LINES, math.ceil(line_count * _REWRITE_CAP_FRACTION))
        if not changed:
            ok5 = False
            detail = (
                "fix replaces or deletes no existing line (pure insertion): "
                "nothing for the exercise to point at"
            )
        elif len(changed) > cap:
            ok5 = False
            detail = (
                f"fix changes {len(changed)} original lines, over the minimal-fix "
                f"cap of {cap}: a rewrite, not a fix"
            )
        else:
            ok5 = True
            verified_bug_lines = changed
            detail = (
                f"verified bug_lines {changed} (diff-derived); "
                f"generator claimed {candidate.bug_lines}"
            )
    else:
        ok5 = candidate.fixed_code == candidate.buggy_code and candidate.bug_lines == []
        verified_bug_lines = [] if ok5 else None
        detail = f"diff says {changed}, candidate says {candidate.bug_lines}"
    checks.append(GateCheck("fix_diff_real_and_minimal", ok5, detail))

    accepted = all(c.passed for c in checks)
    return SandboxGateResult(
        accepted=accepted,
        checks=checks,
        verified_bug_lines=verified_bug_lines if accepted else None,
        bug_lines_claim_mismatch=claim_mismatch,
    )


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
