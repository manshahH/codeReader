"""Pipeline settings.

Deliberately separate from backend/app/config.py: per the module boundary law
(docs/06), pipeline is an independently deployable unit (D-1) and only
publish.py is allowed to reach into backend.app (models/db), so pipeline owns
its own copies of the env vars it needs instead of importing app.config.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class GateModelConflictError(RuntimeError):
    """Raised when GATE_MODEL and GENERATOR_MODEL are configured identically."""


class PipelineSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)

    DATABASE_URL: str = "postgresql://codereader:codereader@localhost:5432/codereader"
    # Optional by design (D-44): the pipeline is OpenAI-only by default and must
    # import/run with no Anthropic key present. Whichever provider is actually
    # selected has its key validated lazily, at client-construction time, in
    # pipeline/llm_client.py -- not here.
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GENERATOR_PROVIDER: str = "openai"
    GATE_PROVIDER: str = "openai"
    GATE_MODEL: str = "gate-model-placeholder"
    GENERATOR_MODEL: str = "generator-model-placeholder"
    # D-80: per-type generator model routing. Empty (the default) means "use
    # GENERATOR_MODEL for spot_the_bug too" -- the routing capability is built
    # but OFF. Set it (e.g. to a stronger model) to route ONLY spot_the_bug
    # generation there while trace and the predict_the_fix distractor step stay
    # on GENERATOR_MODEL; STB is the flagship and the only type worth the
    # premium. One env var flips it on.
    GENERATOR_MODEL_STB: str = ""
    SANDBOX_HOST: str = ""
    VALIDATION_REPORTS_DIR: str = "pipeline/validation_reports"

    # D-83 feedback-driven repair + D-84 best-of-N selection. Both default OFF
    # so existing tests (whose scripted clients queue exactly the primary-path
    # responses) are unaffected; the real batch CLI turns them on. Every value
    # is the explicit, tunable policy the upgrades call for.
    REPAIR_ENABLED: bool = True
    BEST_OF_N_ENABLED: bool = True
    # Total LLM generation calls per spec (fresh + repair). Repairs consume from
    # this cap, so the loop can never spend more than this per spec regardless of
    # how repair/best-of-N interleave.
    MAX_ATTEMPTS_PER_SPEC: int = 4
    # Hard bound on repair rounds within a single candidate lineage (D-83 1c).
    MAX_REPAIR_ROUNDS: int = 2
    # Best-of-N (D-84): at most this many survivors pursued per spec; extra
    # survivors are chased ONLY when the first scores below the threshold or the
    # concept is under-covered, so cost is not blanket-multiplied (D-84 2c).
    BEST_OF_N_MAX_SURVIVORS: int = 2
    BEST_OF_N_SCORE_THRESHOLD: float = 0.70
    BEST_OF_N_COVERAGE_THRESHOLD: int = 2

    def assert_gate_and_generator_models_differ(self) -> None:
        if self.GATE_MODEL == self.GENERATOR_MODEL:
            raise GateModelConflictError(
                "GATE_MODEL must differ from GENERATOR_MODEL (D-14): a model "
                f"grading its own output inherits its own blind spots, got {self.GATE_MODEL!r} "
                "for both.",
            )
        # D-80: the per-type STB override, when set, is still a generator and
        # still must not equal the gate model, for the same D-14 reason.
        if self.GENERATOR_MODEL_STB and self.GENERATOR_MODEL_STB == self.GATE_MODEL:
            raise GateModelConflictError(
                "GENERATOR_MODEL_STB must differ from GATE_MODEL (D-14): a model "
                f"grading its own output inherits its own blind spots, got {self.GATE_MODEL!r} "
                "for both.",
            )

    @property
    def validation_reports_dir(self) -> Path:
        path = Path(self.VALIDATION_REPORTS_DIR)
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path


@lru_cache
def get_pipeline_settings() -> PipelineSettings:
    settings = PipelineSettings()
    settings.assert_gate_and_generator_models_differ()
    return settings
