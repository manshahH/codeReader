"""Offline (mocked-LLM) tests for the pipeline generation-loop upgrades:

  - D-83 feedback-driven repair: classification (repairable vs fundamental),
    a repair triggered with the right evidence, a repaired candidate re-run
    through the FULL gate chain and published, and every hard bound (max repair
    rounds, same-check-twice stop, the MAX_ATTEMPTS_PER_SPEC budget).
  - D-84 best-of-N: the quality score, and selecting the higher-scoring survivor.
  - D-86 prompt caching: the generator prompt's static prefix is spec-independent
    (so it caches), and cost estimation prices cached tokens at the discount.

Every LLM call is a ScriptedLLMClient; no real tokens are spent. The run_batch
tests execute real Docker sandbox passes (same as the existing M3/M8 suites), so
"a repaired candidate still goes through every gate" is proven by execution, not
by mocking the gates away.
"""

from __future__ import annotations

import json

import pytest
from pipeline.config import PipelineSettings
from pipeline.llm_client import ScriptedLLMClient, TokenUsage, estimate_cost_usd
from pipeline.orchestrator import LoopPolicy, run_batch
from pipeline.repair import (
    RepairClass,
    classify_fundamental,
    classify_sandbox,
    classify_static,
)
from pipeline.sandbox_gate import GateCheck, SandboxGateResult
from pipeline.scoring import ScoreSignals, score_survivor
from pipeline.spec_sampler import ExerciseSpec
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exercise

# --------------------------------------------------------------------------- #
# fixtures / builders
# --------------------------------------------------------------------------- #


def _spec(concept: str = "off-by-one", difficulty: int = 3) -> ExerciseSpec:
    return ExerciseSpec(
        type="spot_the_bug",
        concept=concept,
        difficulty=difficulty,
        domain="billing reconciliation",
        line_budget_min=1,
        line_budget_max=20,
        has_bug=True,
        avoid_patterns=(),
    )


def _stb_json(
    *,
    buggy: str,
    fixed: str,
    bug_lines: list[int],
    test: str,
    concept: str = "off-by-one",
    correct_reason_id: str = "a",
    difficulty: int = 3,
) -> dict:
    return {
        "buggy_code": buggy,
        "fixed_code": fixed,
        "bug_lines": bug_lines,
        "test_code": test,
        "context_note": "Runs once per invoice in the billing worker.",
        "reason_options": [
            {"id": "a", "text": "The fee is rounded to too few decimal places."},
            {"id": "b", "text": "The rate is applied twice."},
            {"id": "c", "text": "The amount is negated."},
            {"id": "d", "text": "The loop skips the last element."},
        ],
        "correct_reason_id": correct_reason_id,
        "draft_explanation": {
            "summary": "Rounding to one decimal drops a cent on some inputs.",
            "principle": "Round money to the currency's minor unit.",
            "line_notes": [{"line": (bug_lines[0] if bug_lines else 1), "note": "coarse"}],
        },
        "concepts": [concept],
        "self_difficulty": difficulty,
        "self_check": {
            "single_bug_confirmed": True,
            "runs_without_error_on_happy_path": True,
            "no_hinting_names_or_comments": True,
            "distractors_verifiably_wrong": True,
        },
    }


def _fee(
    test: str, *, buggy: str = "", fixed: str = "", bug_lines: list[int] | None = None,
) -> dict:
    """Short builder for the apply_fee family used across the run_batch tests."""
    return _stb_json(
        buggy=buggy or _BUGGY_1DP,
        fixed=fixed or _FIXED_2DP,
        bug_lines=bug_lines or [2],
        test=test,
    )


# A bug that ROUNDS to 1 decimal instead of 2 (bug_lines=[2]); a real replace diff.
_BUGGY_1DP = "def apply_fee(amount, rate):\n    fee = round(amount * rate, 1)\n    return fee\n"
_FIXED_2DP = "def apply_fee(amount, rate):\n    fee = round(amount * rate, 2)\n    return fee\n"
# NON-discriminating test: at rate 0.5, round(5.0, 1) == round(5.0, 2) == 5.0, so
# the test passes on the buggy code -> buggy_fails_test FAILS (a repairable reject).
_NON_DISCRIMINATING_TEST = (
    "result = apply_fee(10, 0.5)\nprint(repr(result))\nassert result == 5.0, 'fee'\n"
)
# DISCRIMINATING test: at rate 0.125, buggy rounds 1.25 -> 1.2, fixed keeps 1.25.
_DISCRIMINATING_TEST = (
    "result = apply_fee(10, 0.125)\nprint(repr(result))\nassert result == 1.25, 'keep cents'\n"
)


def _defect_audit(lines: list[int]) -> str:
    return json.dumps(
        {"defects": [{"lines": lines, "description": "coarse rounding", "exposed_by": "test"}]},
    )


def _defect_audit_two() -> str:
    return json.dumps(
        {
            "defects": [
                {"lines": [2], "description": "coarse rounding", "exposed_by": "t"},
                {"lines": [1], "description": "a second, unrelated defect", "exposed_by": "t"},
            ],
        },
    )


def _solver(line: int, reason_id: str = "a", confidence: float = 0.9) -> str:
    return json.dumps(
        {
            "answer": {"line": line, "reason_id": reason_id},
            "confidence": confidence,
            "problems_with_the_exercise": [],
        },
    )


_REASONS_OK = json.dumps(
    {
        "verdicts": [
            {"id": "a", "classification": "correct", "justification": "j"},
            {"id": "b", "classification": "wrong", "justification": "j"},
            {"id": "c", "classification": "wrong", "justification": "j"},
            {"id": "d", "classification": "wrong", "justification": "j"},
        ],
    },
)


# --------------------------------------------------------------------------- #
# D-83 classification (pure, no sandbox)
# --------------------------------------------------------------------------- #


def test_classify_static_is_repairable() -> None:
    rejection = classify_static(["forbidden import 'random'"])
    assert rejection.repair_class is RepairClass.REPAIRABLE
    assert rejection.check == "static_gate"
    assert "random" in rejection.evidence


def test_classify_sandbox_repairable_when_only_repairable_checks_fail() -> None:
    result = SandboxGateResult(
        accepted=False,
        checks=[
            GateCheck("buggy_fails_test", passed=False, detail="exit 0, test passed on buggy"),
            GateCheck("fixed_passes_test", passed=True),
            GateCheck("deterministic_double_run", passed=True),
        ],
    )
    rejection = classify_sandbox(result)
    assert rejection.repair_class is RepairClass.REPAIRABLE
    assert rejection.check == "buggy_fails_test"
    assert "test passed on buggy" in rejection.evidence


def test_classify_sandbox_fundamental_when_any_failing_check_is_not_repairable() -> None:
    # buggy_fails_test is repairable, but a nondeterminism failure alongside it is
    # a code property no targeted repair should re-roll -> the whole reject is
    # FUNDAMENTAL (we never partially-trust a candidate).
    result = SandboxGateResult(
        accepted=False,
        checks=[
            GateCheck("buggy_fails_test", passed=False, detail="x"),
            GateCheck("deterministic_double_run", passed=False, detail="nondeterministic"),
        ],
    )
    assert classify_sandbox(result).repair_class is RepairClass.FUNDAMENTAL


def test_semantic_and_dedup_rejections_are_fundamental() -> None:
    assert classify_fundamental("semantic_gate", "defect_audit", "second defect").repair_class is (
        RepairClass.FUNDAMENTAL
    )
    assert classify_fundamental("dedup", "dedup", "dup").repair_class is RepairClass.FUNDAMENTAL


# --------------------------------------------------------------------------- #
# D-84 scoring (pure, no sandbox)
# --------------------------------------------------------------------------- #


def test_score_penalizes_a_hard_exercise_the_solver_breezed() -> None:
    breezed = score_survivor(
        ScoreSignals(
            exercise_type="spot_the_bug",
            authored_difficulty=9,
            solver_confidence=0.99,
            solver_matched=True,
            code_line_count=30,
            verified_bug_lines=(15,),
        ),
    )
    assert breezed.difficulty_miscalibrated is True
    assert "breezed_hard" in breezed.breakdown
    assert breezed.score < 1.0


def test_score_rewards_genuine_struggle_on_a_hard_exercise() -> None:
    struggled = score_survivor(
        ScoreSignals(
            exercise_type="spot_the_bug",
            authored_difficulty=9,
            solver_confidence=0.55,
            solver_matched=True,
            code_line_count=30,
            verified_bug_lines=(15,),
        ),
    )
    assert struggled.difficulty_miscalibrated is False
    assert "genuine_struggle_hard" in struggled.breakdown


def test_score_penalizes_a_bug_visible_in_the_first_two_lines() -> None:
    early = score_survivor(
        ScoreSignals(
            exercise_type="spot_the_bug",
            authored_difficulty=3,
            solver_confidence=0.9,
            solver_matched=True,
            code_line_count=6,
            verified_bug_lines=(2,),
        ),
    )
    late = score_survivor(
        ScoreSignals(
            exercise_type="spot_the_bug",
            authored_difficulty=3,
            solver_confidence=0.9,
            solver_matched=True,
            code_line_count=6,
            verified_bug_lines=(4,),
        ),
    )
    assert early.score < late.score


# --------------------------------------------------------------------------- #
# D-86 caching (pure, no sandbox)
# --------------------------------------------------------------------------- #


def test_generator_prompt_static_prefix_is_spec_independent_for_caching() -> None:
    from pipeline.generate import _render, load_template

    template = load_template("spot_the_bug")
    marker = "## Specification"
    spec_a = _render(
        template.user,
        {
            "python_version": "3.12",
            "concept": "off-by-one",
            "difficulty": 3,
            "domain": "billing reconciliation",
            "line_budget_min": 15,
            "line_budget_max": 30,
            "has_bug": "true",
            "avoid_patterns": "[]",
        },
    )
    spec_b = _render(
        template.user,
        {
            "python_version": "3.12",
            "concept": "aliasing-vs-copy",
            "difficulty": 9,
            "domain": "fraud scoring service",
            "line_budget_min": 40,
            "line_budget_max": 60,
            "has_bug": "false",
            "avoid_patterns": '["x"]',
        },
    )
    prefix_a = spec_a.split(marker)[0]
    prefix_b = spec_b.split(marker)[0]
    # The cacheable prefix (everything before the Specification) is byte-identical
    # across two very different specs, and it carries the expensive worked examples.
    assert prefix_a == prefix_b
    assert "Worked examples" in prefix_a
    assert len(prefix_a) > 2000
    # The varying spec really does differ, and it is at the END.
    assert spec_a != spec_b
    assert spec_a.rstrip().endswith("shipping a constraint violation.")


def test_estimate_cost_prices_cached_prompt_tokens_at_the_discount() -> None:
    fresh = TokenUsage(prompt_tokens=100_000, completion_tokens=0)
    cached = TokenUsage(prompt_tokens=100_000, completion_tokens=0, cached_prompt_tokens=90_000)
    cost_fresh = estimate_cost_usd("gpt-4.1", fresh)
    cost_cached = estimate_cost_usd("gpt-4.1", cached)
    assert cost_cached is not None and cost_fresh is not None
    assert cost_cached < cost_fresh  # 90% of the prompt billed at the cached rate


def test_token_usage_delta_isolates_marginal_spend() -> None:
    before = TokenUsage(prompt_tokens=1000, completion_tokens=200, calls=1)
    after = TokenUsage(prompt_tokens=1500, completion_tokens=260, cached_prompt_tokens=400, calls=2)
    delta = after.delta_since(before)
    assert (delta.prompt_tokens, delta.completion_tokens, delta.calls) == (500, 60, 1)


# --------------------------------------------------------------------------- #
# D-83 repair + D-84 best-of-N end to end (real Docker sandbox)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_repairable_rejection_triggers_repair_with_evidence_and_publishes(
    db_session: AsyncSession,
) -> None:
    # Fresh candidate: real bug, NON-discriminating test -> buggy_fails_test
    # (repairable). Repair returns the same code with a discriminating test ->
    # passes the full chain and publishes.
    fresh = _fee(_NON_DISCRIMINATING_TEST)
    repaired = _fee(_DISCRIMINATING_TEST)
    generator = ScriptedLLMClient([json.dumps(fresh), json.dumps(repaired)])
    # No gate calls for the fresh candidate (sandbox rejects it first); the
    # repaired candidate runs the full semantic chain: defect_audit, solver, reasons.
    gate = ScriptedLLMClient([_defect_audit([2]), _solver(2), _REASONS_OK])

    report = await run_batch(
        db_session,
        1,
        generator_client=generator,
        gate_client=gate,
        generator_model="generator-model-placeholder",
        specs=[_spec()],
        seed_history_from_db=False,
        policy=LoopPolicy(repair_enabled=True, best_of_n_enabled=False, max_attempts_per_spec=4),
    )

    assert report.counts["repair_attempted"] == 1
    assert report.counts["repair_attempted:buggy_fails_test"] == 1
    assert report.counts["repair_succeeded"] == 1
    assert report.counts["published_via_repair"] == 1
    assert report.counts["published_first_try"] == 0
    assert report.counts["published_in_review"] == 1
    # The repair prompt (2nd generator call) named the failed check and carried
    # the original candidate back for a targeted fix.
    repair_prompt = generator.calls[1]["user"]
    assert "buggy_fails_test" in repair_prompt
    assert "apply_fee" in repair_prompt
    # The repaired candidate went through the FULL gate chain, no exemptions: the
    # sandbox passed AND all three semantic gate calls were made.
    assert report.counts["sandbox_gate_passed"] == 1
    assert report.counts["semantic_gate_passed"] == 1
    assert len(gate.calls) == 3


@pytest.mark.asyncio
async def test_fundamental_second_defect_does_not_trigger_repair(
    db_session: AsyncSession,
) -> None:
    # A discriminating candidate that passes the sandbox but whose defect_audit
    # finds a SECOND defect -> FUNDAMENTAL -> never repaired.
    candidate = _fee(_DISCRIMINATING_TEST)
    generator = ScriptedLLMClient([json.dumps(candidate)])
    gate = ScriptedLLMClient([_defect_audit_two()])  # only defect_audit runs (it REJECTs)

    report = await run_batch(
        db_session,
        1,
        generator_client=generator,
        gate_client=gate,
        generator_model="generator-model-placeholder",
        specs=[_spec()],
        seed_history_from_db=False,
        # max_attempts=1 so the fundamental reject exhausts the spec immediately.
        policy=LoopPolicy(repair_enabled=True, best_of_n_enabled=False, max_attempts_per_spec=1),
    )

    assert report.counts["repair_attempted"] == 0
    assert report.counts["published_in_review"] == 0
    assert len(report.spec_exhausted) == 1
    assert len(generator.calls) == 1  # no repair call was made


@pytest.mark.asyncio
async def test_same_check_failing_twice_stops_repair(db_session: AsyncSession) -> None:
    # Fresh AND repaired candidates both fail buggy_fails_test -> after one repair
    # the SAME check fails again, so repairing stops (D-83 1c).
    non_disc_1 = _fee(_NON_DISCRIMINATING_TEST)
    non_disc_2 = _fee(
        "result = apply_fee(20, 0.5)\nprint(repr(result))\nassert result == 10.0, 'fee'\n",
    )
    generator = ScriptedLLMClient([json.dumps(non_disc_1), json.dumps(non_disc_2)])
    gate = ScriptedLLMClient([])  # sandbox rejects both before any gate call

    report = await run_batch(
        db_session,
        1,
        generator_client=generator,
        gate_client=gate,
        generator_model="generator-model-placeholder",
        specs=[_spec()],
        seed_history_from_db=False,
        # 1 fresh + 1 repair = 2 attempts, exactly the budget, so no third fresh.
        policy=LoopPolicy(repair_enabled=True, best_of_n_enabled=False, max_attempts_per_spec=2),
    )

    assert report.counts["repair_attempted"] == 1
    assert report.counts["repair_stopped_same_check"] == 1
    assert report.counts["published_in_review"] == 0
    assert len(report.spec_exhausted) == 1
    assert len(generator.calls) == 2


@pytest.mark.asyncio
async def test_repair_loop_respects_the_attempt_budget_and_cannot_loop_forever(
    db_session: AsyncSession,
) -> None:
    # Every candidate fails a repairable check. With exactly max_attempts_per_spec
    # responses queued, the loop must stop at the budget WITHOUT exhausting the
    # scripted client (which would raise) -- proving it can't loop forever.
    non_disc = _fee(_NON_DISCRIMINATING_TEST)
    generator = ScriptedLLMClient([json.dumps(non_disc)] * 3)
    gate = ScriptedLLMClient([])

    report = await run_batch(
        db_session,
        1,
        generator_client=generator,
        gate_client=gate,
        generator_model="generator-model-placeholder",
        specs=[_spec()],
        seed_history_from_db=False,
        policy=LoopPolicy(repair_enabled=True, best_of_n_enabled=False, max_attempts_per_spec=3),
    )

    assert report.counts["published_in_review"] == 0
    assert len(report.spec_exhausted) == 1
    # Exactly the budget was spent -- no more, no infinite loop.
    assert len(generator.calls) == 3


@pytest.mark.asyncio
async def test_best_of_n_publishes_the_higher_scoring_survivor(db_session: AsyncSession) -> None:
    # Two survivors clear every gate; the first has its bug on line 2 (a scoring
    # penalty), the second on line 4 (no penalty). Best-of-N must publish the
    # second, higher-scoring one.
    buggy_line2 = _BUGGY_1DP  # bug on line 2
    fixed_line2 = _FIXED_2DP
    buggy_line4 = (
        "def apply_fee(amount, rate):\n"
        "    base = amount\n"
        "    scaled = base * rate\n"
        "    fee = round(scaled, 1)\n"
        "    return fee\n"
    )
    fixed_line4 = (
        "def apply_fee(amount, rate):\n"
        "    base = amount\n"
        "    scaled = base * rate\n"
        "    fee = round(scaled, 2)\n"
        "    return fee\n"
    )
    survivor_a = _fee(_DISCRIMINATING_TEST, buggy=buggy_line2, fixed=fixed_line2, bug_lines=[2])
    survivor_b = _fee(_DISCRIMINATING_TEST, buggy=buggy_line4, fixed=fixed_line4, bug_lines=[4])
    generator = ScriptedLLMClient([json.dumps(survivor_a), json.dumps(survivor_b)])
    gate = ScriptedLLMClient(
        [_defect_audit([2]), _solver(2), _REASONS_OK, _defect_audit([4]), _solver(4), _REASONS_OK],
    )

    report = await run_batch(
        db_session,
        1,
        generator_client=generator,
        gate_client=gate,
        generator_model="generator-model-placeholder",
        specs=[_spec()],
        seed_history_from_db=False,
        coverage_driven_sampling=False,  # keep the concept "under-covered" deterministically
        policy=LoopPolicy(
            repair_enabled=False,
            best_of_n_enabled=True,
            max_attempts_per_spec=4,
            best_of_n_max_survivors=2,
            best_of_n_coverage_threshold=2,
        ),
    )

    assert report.counts["best_of_n_pursued"] == 1
    assert report.counts["best_of_n_extra_survivors"] == 1
    assert report.counts["best_of_n_selected_better"] == 1
    assert report.counts["published_in_review"] == 1
    # The published exercise is survivor B (bug on line 4), the higher scorer.
    row = (
        await db_session.scalars(select(Exercise).where(Exercise.status == "in_review"))
    ).one()
    assert "base = amount" in row.payload["code"]
    assert row.grading["correct_lines"] == [4]


def test_settings_default_repair_and_best_of_n_on_for_the_real_batch() -> None:
    # The real batch (CLI) turns both upgrades on; run_batch's own default keeps
    # them off so existing tests are unaffected.
    settings = PipelineSettings()
    assert settings.REPAIR_ENABLED is True
    assert settings.BEST_OF_N_ENABLED is True
    assert LoopPolicy().repair_enabled is False
    assert LoopPolicy().best_of_n_enabled is False
