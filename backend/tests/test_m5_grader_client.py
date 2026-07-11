"""OpenAIGraderClient model-family routing for token-limit/temperature params
(D-47). Mirrors backend/tests/test_m3_llm_client.py's coverage of the same
fix in pipeline/llm_client.py's OpenAILLMClient -- the two clients are
deliberately separate modules (D-43) but share this bug and its fix.

All mocked; no real tokens spent.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.attempts.grader_client import OpenAIGraderClient, _token_limit_kwarg


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("gpt-5", "max_completion_tokens"),
        ("gpt-5-mini", "max_completion_tokens"),
        ("o1", "max_completion_tokens"),
        ("o3-mini", "max_completion_tokens"),
        ("o4-mini", "max_completion_tokens"),
        ("gpt-4o", "max_tokens"),
        ("gpt-4o-mini", "max_tokens"),
        ("gpt-3.5-turbo", "max_tokens"),
    ],
)
def test_token_limit_kwarg_routes_by_model_family(model: str, expected: str) -> None:
    assert _token_limit_kwarg(model) == expected


async def test_gpt5_model_sends_max_completion_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    import openai

    captured: dict[str, object] = {}

    class _FakeCompletions:
        async def create(self, **kwargs: object) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            )

    class _FakeAsyncOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "AsyncOpenAI", _FakeAsyncOpenAI)

    client = OpenAIGraderClient("gpt-5")
    result = await client.complete(system="s", user="u")

    assert result == "ok"
    assert "max_completion_tokens" in captured
    assert "max_tokens" not in captured


async def test_gpt4_model_sends_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    import openai

    captured: dict[str, object] = {}

    class _FakeCompletions:
        async def create(self, **kwargs: object) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            )

    class _FakeAsyncOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "AsyncOpenAI", _FakeAsyncOpenAI)

    client = OpenAIGraderClient("gpt-4o-mini")
    result = await client.complete(system="s", user="u")

    assert result == "ok"
    assert "max_tokens" in captured
    assert "max_completion_tokens" not in captured


async def test_temperature_400_falls_back_to_omitting_temperature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import openai

    calls: list[dict[str, object]] = []

    class _FakeCompletions:
        async def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            if len(calls) == 1:
                raise ValueError(
                    "Unsupported value: 'temperature' does not support 0.0 with this model.",
                )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            )

    class _FakeAsyncOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "AsyncOpenAI", _FakeAsyncOpenAI)

    client = OpenAIGraderClient("gpt-5")
    result = await client.complete(system="s", user="u")

    assert result == "ok"
    assert len(calls) == 2
    assert "temperature" in calls[0]
    assert "temperature" not in calls[1]


async def test_non_temperature_400_still_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import openai

    class _FakeCompletions:
        async def create(self, **kwargs: object) -> SimpleNamespace:
            raise ValueError("invalid_api_key")

    class _FakeAsyncOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "AsyncOpenAI", _FakeAsyncOpenAI)

    client = OpenAIGraderClient("gpt-4o-mini")

    with pytest.raises(ValueError, match="invalid_api_key"):
        await client.complete(system="s", user="u")
