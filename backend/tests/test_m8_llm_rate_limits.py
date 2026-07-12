"""OpenAI rate-limit handling for the content pipeline (M8 part 1).

CLAUDE.md M8: "Handle OpenAI rate limits gracefully: on 429, back off and
RETRY rather than crashing the whole batch (I hit insufficient_quota and
lost a run)." Two distinct 429 shapes need distinct handling:
- transient rate_limit_exceeded (RPM/TPM cap): back off and retry.
- insufficient_quota (billing/plan limit): retrying can never succeed: raise
  a clear, distinct error immediately instead of burning the retry budget.

All calls are mocked; no real tokens spent, no real sleeping (`_sleep` is
monkeypatched to a no-op so the retry-exhaustion test doesn't take a minute).
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import openai
import pytest
from pipeline.config import PipelineSettings
from pipeline.llm_client import (
    OpenAIQuotaExceededError,
    TokenUsage,
    build_llm_client,
    estimate_cost_usd,
)


def _patched_settings(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> PipelineSettings:
    settings = PipelineSettings(**{"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "", **overrides})
    monkeypatch.setattr("pipeline.llm_client.get_pipeline_settings", lambda: settings)
    return settings


def _rate_limit_error(code: str | None) -> openai.RateLimitError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request)
    body = {"message": "rate limited", "code": code} if code else None
    return openai.RateLimitError("rate limited", response=response, body=body)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pipeline.llm_client._sleep", lambda _seconds: None)


def test_transient_rate_limit_retries_and_eventually_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patched_settings(monkeypatch, OPENAI_API_KEY="test-openai-key")

    calls: list[int] = []

    class _FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(1)
            if len(calls) < 3:
                raise _rate_limit_error("rate_limit_exceeded")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )

    class _FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = build_llm_client("openai", "gpt-4o-mini")
    result = client.complete(system="s", user="u", temperature=0.2)

    assert result == "ok"
    assert len(calls) == 3  # two failures, then success -- no exception raised
    assert client.usage.prompt_tokens == 10
    assert client.usage.completion_tokens == 5


def test_rate_limit_retries_are_exhausted_and_the_last_error_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patched_settings(monkeypatch, OPENAI_API_KEY="test-openai-key")

    class _FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            raise _rate_limit_error("rate_limit_exceeded")

    class _FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = build_llm_client("openai", "gpt-4o-mini")

    with pytest.raises(openai.RateLimitError):
        client.complete(system="s", user="u", temperature=0.2)


def test_insufficient_quota_raises_immediately_without_retrying(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    _patched_settings(monkeypatch, OPENAI_API_KEY="test-openai-key")

    class _FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(1)
            raise _rate_limit_error("insufficient_quota")

    class _FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = build_llm_client("openai", "gpt-4o-mini")

    with pytest.raises(OpenAIQuotaExceededError, match="insufficient_quota"):
        client.complete(system="s", user="u", temperature=0.2)

    assert len(calls) == 1  # no retries burned on an unrecoverable billing error


def test_token_usage_accumulates_across_multiple_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_settings(monkeypatch, OPENAI_API_KEY="test-openai-key")

    class _FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
                usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
            )

    class _FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = build_llm_client("openai", "gpt-4.1")
    client.complete(system="s", user="u", temperature=0.8)
    client.complete(system="s", user="u", temperature=0.8)

    assert client.usage.calls == 2
    assert client.usage.prompt_tokens == 200
    assert client.usage.completion_tokens == 40
    assert client.usage.total_tokens == 240


def test_estimate_cost_usd_known_model() -> None:
    usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    cost = estimate_cost_usd("gpt-4.1", usage)
    assert cost == pytest.approx(2.00 + 8.00)


def test_estimate_cost_usd_unknown_model_returns_none() -> None:
    usage = TokenUsage(prompt_tokens=1_000, completion_tokens=1_000)
    assert estimate_cost_usd("some-future-model", usage) is None
