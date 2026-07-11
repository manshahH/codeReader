"""Seed scripts cannot silently write gate-bypassing 'live' content (audit
FIX 4). Negative tests first: the guard's whole job is to refuse.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from scripts.seed_e2e import EXERCISES as E2E_EXERCISES
from scripts.seed_guard import require_seed_flag, validate_concepts
from scripts.seed_summarize_exercises import EXERCISES as SUMMARIZE_EXERCISES
from tests.factories_m4 import (
    m4_env,  # noqa: F401 (autouse fixture, must be imported to activate)
)


def test_seeding_refuses_without_the_explicit_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEREADER_ALLOW_SEED", raising=False)
    get_settings.cache_clear()

    with pytest.raises(SystemExit, match="refusing to seed"):
        require_seed_flag()


def test_seeding_proceeds_with_the_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEREADER_ALLOW_SEED", "1")
    get_settings.cache_clear()

    require_seed_flag()  # must not raise


def test_unknown_concept_slug_is_refused() -> None:
    specs = [{"concepts": ["mutable-default-arg", "list-indexing"]}]

    with pytest.raises(SystemExit, match="list-indexing"):
        validate_concepts(specs)


def test_all_shipped_seed_specs_use_taxonomy_concepts() -> None:
    """The actual seed content stays honest: every slug the seeds stamp onto
    exercises resolves in the taxonomy (the old trace seed's 'list-indexing'
    did not, and polluted user_concept_state on every attempt)."""
    validate_concepts(E2E_EXERCISES)
    validate_concepts(SUMMARIZE_EXERCISES)
