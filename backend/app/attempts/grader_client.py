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


# gpt-5*, o1, o3, o4 reject `max_tokens` ("Unsupported parameter: 'max_tokens'
# is not supported with this model. Use 'max_completion_tokens' instead");
# gpt-4* and earlier still expect `max_tokens` (D-47, mirrors
# pipeline/llm_client.py's _token_limit_kwarg).
_LEGACY_MAX_TOKENS_PREFIXES = ("gpt-4", "gpt-3")


def _token_limit_kwarg(model: str) -> str:
    """Name of the token-limit kwarg this model family expects.

    Unknown/future families default to `max_completion_tokens` (the newer
    param); `complete()` falls back to `max_tokens` at runtime if the API
    400s naming it instead.
    """
    if model.startswith(_LEGACY_MAX_TOKENS_PREFIXES):
        return "max_tokens"
    return "max_completion_tokens"


class OpenAIGraderClient:
    """Real OpenAI-backed client, same Protocol shape as the Anthropic one.

    D-43: an alternative provider for GRADER_PROVIDER="openai" -- the grader
    is a self-contained seam (docs/06 D-18) precisely so its LLM backend can
    be swapped without touching attempts/service.py or rubric.py.
    """

    def __init__(self, model: str, max_tokens: int = 1024) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is None:
            import openai

            self._client = openai.AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
        return self._client

    async def complete(self, *, system: str, user: str) -> str:
        client = self._get_client()
        token_kwarg = _token_limit_kwarg(self._model)
        kwargs: dict[str, object] = {
            "model": self._model,
            token_kwarg: self._max_tokens,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as exc:
            # D-47: gpt-5-family models reject max_tokens (retry with
            # max_completion_tokens) and reasoning models can 400 on a
            # non-default temperature (retry with it omitted).
            message = str(exc)
            retry_kwargs = dict(kwargs)
            changed = False
            if token_kwarg == "max_completion_tokens" and "max_tokens" in message:
                retry_kwargs["max_tokens"] = retry_kwargs.pop("max_completion_tokens")
                changed = True
            if "temperature" in message:
                retry_kwargs.pop("temperature", None)
                changed = True
            if not changed:
                raise
            response = await client.chat.completions.create(**retry_kwargs)
        return response.choices[0].message.content or ""


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
        provider = get_settings().GRADER_PROVIDER
        if provider == "openai":
            _default_client = OpenAIGraderClient(model)
        elif provider == "anthropic":
            _default_client = AnthropicGraderClient(model)
        else:
            raise ValueError(f"Unknown GRADER_PROVIDER: {provider!r}")
    return _default_client
