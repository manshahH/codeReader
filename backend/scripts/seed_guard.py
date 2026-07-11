"""Guard rails for the hand-authored seed scripts (audit FIX 4).

Seed scripts insert exercises as status='live', human_reviewed=True with
hand-written answer keys -- content that never went through the sandbox or
the gates. That is acceptable ONLY as a deliberate dev/e2e action against a
throwaway database, never as something that can silently run against
whatever DATABASE_URL happens to point at (a shared or beta DB). Two rails:

1. `require_seed_flag()`: the script refuses to run unless
   CODEREADER_ALLOW_SEED=1 (or true) is set explicitly, so pointing the
   script at a real database requires a conscious, per-invocation opt-in.
2. `validate_concepts()`: every concept slug must exist in the pipeline
   taxonomy. A made-up slug (the old trace seed used "list-indexing", which
   is not in the taxonomy) flows into user_concept_state on every attempt
   and permanently pollutes the skill graph and the spaced-repetition state.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    # pipeline/ lives at the repo root, outside the installed `app` package.
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline import taxonomy  # noqa: E402

from app.config import get_settings  # noqa: E402


def require_seed_flag() -> None:
    if get_settings().CODEREADER_ALLOW_SEED:
        return
    raise SystemExit(
        "refusing to seed: seed content bypasses the sandbox and review gates"
        " and must never reach a shared database. If this database is truly"
        " disposable (local dev / e2e), re-run with CODEREADER_ALLOW_SEED=1.",
    )


def validate_concepts(specs: list[dict[str, Any]]) -> None:
    unknown: set[str] = set()
    for spec in specs:
        for slug in spec.get("concepts", []):
            try:
                taxonomy.get_concept(slug)
            except KeyError:
                unknown.add(slug)
    if unknown:
        raise SystemExit(
            f"refusing to seed: concepts not in the taxonomy: {sorted(unknown)}."
            " Unknown slugs pollute user_concept_state and the skill graph.",
        )
