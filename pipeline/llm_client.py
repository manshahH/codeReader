"""LLM client abstraction.

generate.py and semantic_gates.py depend only on the `LLMClient` protocol.
`AnthropicLLMClient` is the real implementation and is never constructed in
tests; `ScriptedLLMClient` is the fixture/mock double used by tests and by the
orchestrator's --mock mode, so pipeline tests never spend a real token
(CLAUDE.md: "LLM calls are mocked in backend tests").
"""

from __future__ import annotations

from typing import Protocol

from pipeline.config import get_pipeline_settings


class LLMClient(Protocol):
    def complete(self, *, system: str, user: str, temperature: float) -> str: ...


class AnthropicLLMClient:
    """Real Anthropic-backed client. Constructed lazily; never touched in tests."""

    def __init__(self, model: str, max_tokens: int = 4096) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=get_pipeline_settings().ANTHROPIC_API_KEY)
        return self._client

    def complete(self, *, system: str, user: str, temperature: float) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


class ScriptedLLMClient:
    """Test/demo double: returns canned responses in order, one per call."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def complete(self, *, system: str, user: str, temperature: float) -> str:
        self.calls.append({"system": system, "user": user, "temperature": temperature})
        if not self._responses:
            raise RuntimeError("ScriptedLLMClient exhausted: no more responses queued")
        return self._responses.pop(0)
