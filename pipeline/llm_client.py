"""LLM client abstraction.

generate.py and semantic_gates.py depend only on the `LLMClient` protocol.
`AnthropicLLMClient` and `OpenAILLMClient` are the real implementations and
are never constructed in tests; `ScriptedLLMClient` is the fixture/mock
double used by tests and by the orchestrator's --mock mode, so pipeline
tests never spend a real token (CLAUDE.md: "LLM calls are mocked in backend
tests").

The pipeline is OpenAI-only by default (D-44): `build_llm_client()` is the
single place that turns a provider name into a client, driven by
GENERATOR_PROVIDER/GATE_PROVIDER + the matching model var. Each client
validates its own API key lazily, inside `_get_client()`, so importing and
constructing pipeline settings never requires an Anthropic key -- only
actually using the anthropic provider does.
"""

from __future__ import annotations

import logging
from typing import Protocol

from pipeline.config import get_pipeline_settings

logger = logging.getLogger(__name__)


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
            api_key = get_pipeline_settings().ANTHROPIC_API_KEY
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY is required to use provider='anthropic' but is not set",
                )
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key)
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


# gpt-5*, o1, o3, o4 reject `max_tokens` ("Unsupported parameter: 'max_tokens'
# is not supported with this model. Use 'max_completion_tokens' instead");
# gpt-4* and earlier still expect `max_tokens` (D-47).
_LEGACY_MAX_TOKENS_PREFIXES = ("gpt-4", "gpt-3")

# gpt-5-family and o* reasoning models 400 on any non-default temperature.
# Known families are resolved UP FRONT (D-55) -- sending temperature first and
# eating the guaranteed 400 doubled every request against rate limits, and the
# silent retry-without-temperature also hid that the semantic gates' designed
# temp 0 was not being honored.
_FIXED_TEMPERATURE_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def _token_limit_kwarg(model: str) -> str:
    """Name of the token-limit kwarg this model family expects.

    Unknown/future families default to `max_completion_tokens` (the newer
    param); `complete()` falls back to `max_tokens` at runtime if the API
    400s naming it instead.
    """
    if model.startswith(_LEGACY_MAX_TOKENS_PREFIXES):
        return "max_tokens"
    return "max_completion_tokens"


def _supports_custom_temperature(model: str) -> bool:
    return not model.startswith(_FIXED_TEMPERATURE_PREFIXES)


class OpenAILLMClient:
    """Real OpenAI-backed client, same shape as AnthropicLLMClient (D-44).

    Mirrors backend/app/attempts/grader_client.py's OpenAIGraderClient, the
    reference pattern from D-43, adapted to this module's sync Protocol.
    """

    def __init__(self, model: str, max_tokens: int = 4096) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = None
        self._warned_fixed_temperature = False

    def _get_client(self):
        if self._client is None:
            api_key = get_pipeline_settings().OPENAI_API_KEY
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY is required to use provider='openai' but is not set",
                )
            import openai

            self._client = openai.OpenAI(api_key=api_key)
        return self._client

    def complete(self, *, system: str, user: str, temperature: float) -> str:
        client = self._get_client()
        token_kwarg = _token_limit_kwarg(self._model)
        kwargs: dict[str, object] = {
            "model": self._model,
            token_kwarg: self._max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if _supports_custom_temperature(self._model):
            kwargs["temperature"] = temperature
        elif not self._warned_fixed_temperature:
            # Never silent (D-55): callers designed around a temperature
            # (generator 0.8 for variety, semantic gates 0.0 as judges) must
            # know when the chosen model cannot honor it.
            logger.warning(
                "model %s only supports its default temperature; requested "
                "temperature=%s will not be honored (semantic gates designed "
                "for temp 0 may be noisier on this model)",
                self._model,
                temperature,
            )
            self._warned_fixed_temperature = True
        try:
            response = client.chat.completions.create(**kwargs)
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
            response = client.chat.completions.create(**retry_kwargs)
        return response.choices[0].message.content or ""


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


def build_llm_client(provider: str, model: str) -> LLMClient:
    """Provider name -> real LLMClient (D-44). Construction stays lazy either
    way: this never touches the network or reads an API key itself, so it is
    safe to call regardless of which keys are configured. The key for
    whichever provider you pass is only checked when `complete()` is
    eventually called.
    """
    if provider == "anthropic":
        return AnthropicLLMClient(model)
    if provider == "openai":
        return OpenAILLMClient(model)
    raise ValueError(f"Unknown LLM provider: {provider!r} (expected 'anthropic' or 'openai')")
