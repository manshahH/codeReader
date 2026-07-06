from pathlib import Path

from app.config import Settings


def _env_example_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env.example"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(".env.example")


def _env_example_keys() -> set[str]:
    keys: set[str] = set()
    for line in _env_example_path().read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, _, _value = stripped.partition("=")
        keys.add(key)
    return keys


def test_env_example_covers_settings_without_drift() -> None:
    settings_keys = set(Settings.model_fields)
    assert _env_example_keys() == settings_keys
