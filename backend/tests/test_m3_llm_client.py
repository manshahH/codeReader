"""LLM provider wiring for the content pipeline (D-44).

Covers: build_llm_client() provider selection, the pipeline loading and
building clients with only an OpenAI key present (no Anthropic key at all),
per-provider missing-key errors raised lazily at client-construction time,
and that D-14's gate/generator model conflict check still fires. All mocked;
no real tokens spent.

Settings are constructed directly (PipelineSettings(...)) or via a patched
pipeline.llm_client.get_pipeline_settings, never via the real cached
get_pipeline_settings() + env vars: a real .env file with a real
ANTHROPIC_API_KEY exists in this dev checkout, and pydantic-settings reads
env_file values independently of os.environ, so monkeypatch.delenv alone
would not simulate "no Anthropic key present".
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pipeline.config import GateModelConflictError, PipelineSettings
from pipeline.llm_client import (
    AnthropicLLMClient,
    OpenAILLMClient,
    _token_limit_kwarg,
    build_llm_client,
)


def _patched_settings(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> PipelineSettings:
    """Build a PipelineSettings with no Anthropic/OpenAI key by default, and
    make it the one pipeline.llm_client sees -- hermetic against the real
    dev .env file and the module-level settings cache.
    """
    settings = PipelineSettings(**{"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "", **overrides})
    monkeypatch.setattr("pipeline.llm_client.get_pipeline_settings", lambda: settings)
    return settings


# --- build_llm_client() provider selection -----------------------------------


def test_build_llm_client_returns_openai_client_for_openai_provider() -> None:
    client = build_llm_client("openai", "gpt-4o-mini")

    assert isinstance(client, OpenAILLMClient)


def test_build_llm_client_returns_anthropic_client_for_anthropic_provider() -> None:
    client = build_llm_client("anthropic", "claude-haiku")

    assert isinstance(client, AnthropicLLMClient)


def test_build_llm_client_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        build_llm_client("not-a-real-provider", "some-model")


# --- settings + clients build with ONLY an OpenAI key, no Anthropic key -----


def test_pipeline_settings_load_with_only_openai_key_no_anthropic_key() -> None:
    settings = PipelineSettings(
        ANTHROPIC_API_KEY="",
        OPENAI_API_KEY="test-openai-key",
        GENERATOR_PROVIDER="openai",
        GATE_PROVIDER="openai",
    )

    assert settings.ANTHROPIC_API_KEY == ""
    assert settings.OPENAI_API_KEY == "test-openai-key"
    assert settings.GENERATOR_PROVIDER == "openai"
    assert settings.GATE_PROVIDER == "openai"
    settings.assert_gate_and_generator_models_differ()  # must not raise


def test_openai_client_completes_with_only_openai_key_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patched_settings(monkeypatch, OPENAI_API_KEY="test-openai-key")

    import openai

    class _FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="mock completion"))],
            )

    class _FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.api_key = api_key
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = build_llm_client("openai", "gpt-4o-mini")
    result = client.complete(system="be terse", user="2+2?", temperature=0.0)

    assert result == "mock completion"


# --- D-47: gpt-5-family token-limit param + temperature fallback ------------


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("gpt-5", "max_completion_tokens"),
        ("gpt-5-mini", "max_completion_tokens"),
        ("o1", "max_completion_tokens"),
        ("o1-mini", "max_completion_tokens"),
        ("o3", "max_completion_tokens"),
        ("o4-mini", "max_completion_tokens"),
        ("gpt-4o", "max_tokens"),
        ("gpt-4o-mini", "max_tokens"),
        ("gpt-4-turbo", "max_tokens"),
        ("gpt-3.5-turbo", "max_tokens"),
    ],
)
def test_token_limit_kwarg_routes_by_model_family(model: str, expected: str) -> None:
    assert _token_limit_kwarg(model) == expected


def test_gpt5_model_sends_max_completion_tokens_and_no_temperature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # D-55: known fixed-temperature families never receive temperature, so
    # there is no doomed first call to eat a 400 on.
    _patched_settings(monkeypatch, OPENAI_API_KEY="test-openai-key")

    import openai

    calls: list[dict[str, object]] = []

    class _FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            )

    class _FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = build_llm_client("openai", "gpt-5")
    client.complete(system="s", user="u", temperature=0.2)

    assert len(calls) == 1  # exactly one request, no 400-retry pair
    assert "max_completion_tokens" in calls[0]
    assert "max_tokens" not in calls[0]
    assert "temperature" not in calls[0]


def test_fixed_temperature_family_logs_a_warning_instead_of_silence(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # D-55: a gate designed for temp 0 running on a fixed-temperature model
    # must be visible in the logs, not silently different.
    _patched_settings(monkeypatch, OPENAI_API_KEY="test-openai-key")

    import openai

    class _FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            )

    class _FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    # conftest's alembic upgrade runs logging fileConfig with
    # disable_existing_loggers, which flips .disabled on every logger already
    # imported at collection time; re-enable ours so caplog can see it.
    import logging

    monkeypatch.setattr(logging.getLogger("pipeline.llm_client"), "disabled", False)

    client = build_llm_client("openai", "o3")
    with caplog.at_level("WARNING", logger="pipeline.llm_client"):
        client.complete(system="s", user="u", temperature=0.0)
        client.complete(system="s", user="u", temperature=0.0)

    warnings = [r for r in caplog.records if "default temperature" in r.getMessage()]
    assert len(warnings) == 1  # once per client, not per call


def test_gpt4_model_sends_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_settings(monkeypatch, OPENAI_API_KEY="test-openai-key")

    import openai

    captured: dict[str, object] = {}

    class _FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            )

    class _FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = build_llm_client("openai", "gpt-4o-mini")
    client.complete(system="s", user="u", temperature=0.2)

    assert "max_tokens" in captured
    assert "max_completion_tokens" not in captured
    assert captured["temperature"] == 0.2


def test_max_tokens_400_falls_back_to_max_completion_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ambiguous/unknown family name still routes to max_completion_tokens
    up front (D-47); this covers the reverse case, a model reported by the
    API as needing max_tokens after all.
    """
    _patched_settings(monkeypatch, OPENAI_API_KEY="test-openai-key")

    import openai

    calls: list[dict[str, object]] = []

    class _FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            if len(calls) == 1:
                raise ValueError(
                    "Unsupported parameter: 'max_completion_tokens'. Use 'max_tokens' instead.",
                )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            )

    class _FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = build_llm_client("openai", "gpt-6-future")
    result = client.complete(system="s", user="u", temperature=0.2)

    assert result == "ok"
    assert len(calls) == 2
    assert "max_completion_tokens" in calls[0]
    assert "max_tokens" in calls[1]


def test_temperature_400_falls_back_to_omitting_temperature_for_unknown_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # D-55 resolves KNOWN families (gpt-5*/o1/o3/o4) up front; an unknown
    # future family still gets temperature optimistically and keeps the D-47
    # runtime fallback when the API rejects it.
    _patched_settings(monkeypatch, OPENAI_API_KEY="test-openai-key")

    import openai

    calls: list[dict[str, object]] = []

    class _FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            if len(calls) == 1:
                raise ValueError(
                    "Unsupported value: 'temperature' does not support 0.2 with this model.",
                )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            )

    class _FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = build_llm_client("openai", "gpt-6-future")
    result = client.complete(system="s", user="u", temperature=0.2)

    assert result == "ok"
    assert len(calls) == 2
    assert "temperature" in calls[0]
    assert "temperature" not in calls[1]


def test_non_temperature_400_still_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_settings(monkeypatch, OPENAI_API_KEY="test-openai-key")

    import openai

    class _FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            raise ValueError("invalid_api_key")

    class _FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = build_llm_client("openai", "gpt-4o-mini")

    with pytest.raises(ValueError, match="invalid_api_key"):
        client.complete(system="s", user="u", temperature=0.2)


# --- per-provider missing-key errors, raised lazily at construction time ----


def test_openai_provider_with_no_openai_key_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patched_settings(monkeypatch)  # OPENAI_API_KEY="" by default

    client = build_llm_client("openai", "gpt-4o-mini")

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        client.complete(system="s", user="u", temperature=0.0)


def test_anthropic_provider_with_no_anthropic_key_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patched_settings(monkeypatch)  # ANTHROPIC_API_KEY="" by default

    client = build_llm_client("anthropic", "claude-haiku")

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        client.complete(system="s", user="u", temperature=0.0)


# --- D-14: gate model must still differ from generator model ----------------


def test_gate_and_generator_model_equality_still_rejected() -> None:
    settings = PipelineSettings(
        OPENAI_API_KEY="test-key",
        GATE_MODEL="same-model",
        GENERATOR_MODEL="same-model",
    )

    with pytest.raises(GateModelConflictError):
        settings.assert_gate_and_generator_models_differ()
