"""LLM client for the M5 inline rubric grader.

Deliberately separate from pipeline/llm_client.py: the grader runs inline
inside the API process itself (D-18), not in the pipeline's independently
deployable unit (D-33), so it has no reason to share that module. Mirrors its
shape (a Protocol + a real client + a scripted test double) on purpose.
"""

from __future__ import annotations

from typing import Protocol

from app.config import get_settings


class GraderLLMClient(Protocol):
    async def complete(self, *, system: str, user: str) -> str: ...


class AnthropicGraderClient:
    """Real Anthropic-backed client. Constructed lazily; never touched in tests."""

    def __init__(self, model: str, max_tokens: int = 1024) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=get_settings().ANTHROPIC_API_KEY)
        return self._client

    async def complete(self, *, system: str, user: str) -> str:
        client = self._get_client()
        response = await client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=0.0,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


class ScriptedGraderClient:
    """Test double: queued outcomes consumed in call order.

    An outcome may be a raw response string, or an Exception instance to
    simulate a transport/timeout failure on that call. Every call is recorded
    (system + user prompt) so tests can assert the delimited data channel
    held: the raw answer text landed only inside <student_answer>, never in
    the instruction text.
    """

    def __init__(self, outcomes: list[str | Exception]) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict[str, str]] = []

    async def complete(self, *, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        if not self._outcomes:
            raise RuntimeError("ScriptedGraderClient exhausted: no more outcomes queued")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


_default_client: GraderLLMClient | None = None


def get_default_grader_client(model: str) -> GraderLLMClient:
    global _default_client
    if _default_client is None:
        _default_client = AnthropicGraderClient(model)
    return _default_client
