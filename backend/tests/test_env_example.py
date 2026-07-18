"""Both .env.example files are drift-checked, each against its own contract
(D-117).

The original test walked up from here and validated the FIRST .env.example it
found -- backend/.env.example. The ROOT .env.example was therefore never checked
by anything, and had already drifted (it was missing the pipeline's
VALIDATION_REPORTS_DIR). That is the dangerous direction: updating only the
backend file leaves the root file stale with a green suite.

The two files have DIFFERENT contracts and are not duplicates:
  backend/.env.example -> exactly the backend's Settings
  root/.env.example    -> the shared file, so Settings PLUS PipelineSettings
                          (config.py's comments call this out: backend knobs are
                          mirrored there so the shared file stays drift-free
                          against the pipeline, D-44/D-80).
"""

from pathlib import Path

from pipeline.config import PipelineSettings

from app.config import Settings

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ENV = _REPO_ROOT / "backend" / ".env.example"
_ROOT_ENV = _REPO_ROOT / ".env.example"


def _keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, _, _value = stripped.partition("=")
        keys.add(key)
    return keys


def test_both_env_examples_exist() -> None:
    """Guards the guard: if one is deleted, that should be a deliberate edit
    here, not a silent weakening back to checking a single file.
    """
    assert _BACKEND_ENV.exists(), _BACKEND_ENV
    assert _ROOT_ENV.exists(), _ROOT_ENV


def test_backend_env_example_covers_settings_without_drift() -> None:
    assert _keys(_BACKEND_ENV) == set(Settings.model_fields)


def test_root_env_example_covers_settings_and_pipeline_without_drift() -> None:
    expected = set(Settings.model_fields) | set(PipelineSettings.model_fields)
    assert _keys(_ROOT_ENV) == expected
