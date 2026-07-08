"""Pipeline settings.

Deliberately separate from backend/app/config.py: per the module boundary law
(docs/06), pipeline is an independently deployable unit (D-1) and only
publish.py is allowed to reach into backend.app (models/db), so pipeline owns
its own copies of the env vars it needs instead of importing app.config.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class GateModelConflictError(RuntimeError):
    """Raised when GATE_MODEL and GENERATOR_MODEL are configured identically."""


class PipelineSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)

    DATABASE_URL: str = "postgresql://codereader:codereader@localhost:5432/codereader"
    ANTHROPIC_API_KEY: str = Field(..., min_length=1)
    GATE_MODEL: str = "gate-model-placeholder"
    GENERATOR_MODEL: str = "generator-model-placeholder"
    SANDBOX_HOST: str = ""
    VALIDATION_REPORTS_DIR: str = "pipeline/validation_reports"

    def assert_gate_and_generator_models_differ(self) -> None:
        if self.GATE_MODEL == self.GENERATOR_MODEL:
            raise GateModelConflictError(
                "GATE_MODEL must differ from GENERATOR_MODEL (D-14): a model "
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
