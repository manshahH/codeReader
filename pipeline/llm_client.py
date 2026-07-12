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

import dataclasses
import logging
import time
from typing import Protocol

from pipeline.config import get_pipeline_settings

logger = logging.getLogger(__name__)

# Test hook: monkeypatched to a no-op so rate-limit-retry tests don't actually
# sleep. Real runs always go through time.sleep.
_sleep = time.sleep


class LLMClient(Protocol):
    def complete(self, *, system: str, user: str, temperature: float) -> str: ...


@dataclasses.dataclass
class TokenUsage:
    """Cumulative token usage for one client instance across every `complete()`
    call it has served, so a batch report can total spend per role
    (generator/gate) without threading counters through generate.py/
    semantic_gates.py, which only depend on the LLMClient protocol.

    `cached_prompt_tokens` (D-85) is the subset of `prompt_tokens` OpenAI served
    from its prompt cache -- the static system/template prefix billed at a
    discount instead of fresh. It is a SUBSET of prompt_tokens, never additive,
    so total_tokens stays prompt+completion.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_prompt_tokens: int = 0
    calls: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def record(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        cached_prompt_tokens: int = 0,
    ) -> None:
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.cached_prompt_tokens += cached_prompt_tokens
        self.calls += 1

    def delta_since(self, other: TokenUsage) -> TokenUsage:
        """This usage minus an earlier snapshot -- the spend of the calls made
        between the snapshot and now. Used by the orchestrator to attribute the
        MARGINAL cost of a repair (its extra generation call + the extra gate
        pass re-validating the repaired candidate) to the repair bucket, so a
        batch report can answer 'did repair pay for itself?' honestly (D-83).
        """
        return TokenUsage(
            prompt_tokens=self.prompt_tokens - other.prompt_tokens,
            completion_tokens=self.completion_tokens - other.completion_tokens,
            cached_prompt_tokens=self.cached_prompt_tokens - other.cached_prompt_tokens,
            calls=self.calls - other.calls,
        )


# Rough $/1M-token pricing for models this project actually pins (GENERATOR_MODEL
# =gpt-4.1 / GATE_MODEL=gpt-4o since D-81, up from the too-weak gpt-4o-mini) plus
# a couple of common neighbors, so a batch report can show an estimated cost, not
# just token counts. An unrecognized model just skips the cost line (tokens still
# report) rather than guessing -- this table decays as OpenAI reprices models;
# correct it here when it does.
PRICING_USD_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    # D-81: stronger-gate alternatives. gpt-5-mini is smarter but cannot honor
    # temperature=0 (D-55), so it is documented, not the default. Prices are
    # best-effort and, like the rest of this table, corrected when OpenAI moves.
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5": (1.25, 10.00),
}

# D-85: cached-input price per 1M tokens for OpenAI prompt caching. A cached
# prompt token (a hit on the static system/template prefix) bills at this rate
# instead of the full input price. Best-effort, corrected alongside the table
# above when OpenAI reprices. An unlisted model falls back to full input price
# (no discount assumed), so the estimate is conservative, never optimistic.
CACHED_INPUT_USD_PER_1M_TOKENS: dict[str, float] = {
    "gpt-4.1": 0.50,
    "gpt-4.1-mini": 0.10,
    "gpt-4o": 1.25,
    "gpt-4o-mini": 0.075,
    "gpt-5-mini": 0.025,
    "gpt-5": 0.125,
}


def estimate_cost_usd(model: str, usage: TokenUsage) -> float | None:
    pricing = PRICING_USD_PER_1M_TOKENS.get(model)
    if pricing is None:
        return None
    input_price, output_price = pricing
    # D-85: split prompt tokens into fresh vs cache-hit and price each. Cached
    # tokens are a subset of prompt_tokens, so the fresh portion is the
    # remainder; an unpriced-for-cache model just pays full price on all of it.
    cached = max(0, min(usage.cached_prompt_tokens, usage.prompt_tokens))
    fresh = usage.prompt_tokens - cached
    cached_price = CACHED_INPUT_USD_PER_1M_TOKENS.get(model, input_price)
    return (
        (fresh / 1_000_000) * input_price
        + (cached / 1_000_000) * cached_price
        + (usage.completion_tokens / 1_000_000) * output_price
    )


class AnthropicLLMClient:
    """Real Anthropic-backed client. Constructed lazily; never touched in tests."""

    def __init__(self, model: str, max_tokens: int = 4096) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = None
        self.usage = TokenUsage()

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
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.usage.record(
                prompt_tokens=getattr(usage, "input_tokens", 0) or 0,
                completion_tokens=getattr(usage, "output_tokens", 0) or 0,
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


def _prompt_cache_key(system: str) -> str:
    """Stable per-static-prefix routing key for OpenAI prompt caching (D-85).

    Derived from the (spec-independent) system prompt so every generator/gate
    call sharing the same template body maps to the same cache key. A hash, not
    the prompt itself, keeps the key short and free of prompt content.
    """
    import hashlib

    return "codereader-" + hashlib.sha256(system.encode("utf-8")).hexdigest()[:24]


class OpenAIQuotaExceededError(RuntimeError):
    """OpenAI reported insufficient_quota: a billing/plan problem, not a
    transient rate limit. Retrying will never succeed on its own, so this is
    raised immediately instead of being swallowed into the backoff loop
    (CLAUDE.md M8: "I hit insufficient_quota and lost a run" -- the fix is to
    fail loud and distinctly, not to retry forever).
    """


# A content-run batch (~30-40 candidates x several LLM calls each) can hit a
# transient per-minute rate limit repeatedly; back off and retry rather than
# crashing the whole batch and losing every candidate after the failure
# point.
_MAX_RATE_LIMIT_RETRIES = 5
_RATE_LIMIT_BASE_DELAY_S = 2.0
_RATE_LIMIT_MAX_DELAY_S = 60.0


def _is_insufficient_quota(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code == "insufficient_quota":
        return True
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        inner = body.get("error")
        if isinstance(inner, dict) and inner.get("code") == "insufficient_quota":
            return True
    return "insufficient_quota" in str(exc)


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
        self.usage = TokenUsage()

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

    def _create_with_rate_limit_retry(self, client, kwargs: dict[str, object]):
        import openai

        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            try:
                return client.chat.completions.create(**kwargs)
            except openai.RateLimitError as exc:
                if _is_insufficient_quota(exc):
                    raise OpenAIQuotaExceededError(
                        f"OpenAI reports insufficient_quota for model {self._model!r}. "
                        "This is a billing/plan limit, not a transient rate limit -- "
                        "add credit or raise the quota before re-running the batch. "
                        "Candidates published before this point are already committed.",
                    ) from exc
                if attempt >= _MAX_RATE_LIMIT_RETRIES:
                    raise
                delay = min(
                    _RATE_LIMIT_BASE_DELAY_S * (2**attempt),
                    _RATE_LIMIT_MAX_DELAY_S,
                )
                logger.warning(
                    "OpenAI rate limited (attempt %d/%d) for model %s; backing off %.1fs",
                    attempt + 1,
                    _MAX_RATE_LIMIT_RETRIES,
                    self._model,
                    delay,
                )
                _sleep(delay)
        raise AssertionError("unreachable: retry loop always returns or raises")

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
            # D-85: route by the static prefix so OpenAI's prompt cache is hit
            # consistently across a batch. The generator templates are
            # restructured (spec LAST) so system + the template body form one
            # large, spec-independent prefix; a per-system-prompt key groups
            # every call that shares that prefix. Automatic prefix caching works
            # without this, but the key stabilizes routing under concurrency.
            "prompt_cache_key": _prompt_cache_key(system),
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
            response = self._create_with_rate_limit_retry(client, kwargs)
        except Exception as exc:
            if isinstance(exc, OpenAIQuotaExceededError):
                raise
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
            # D-85: an SDK/model too old for prompt_cache_key rejects the kwarg;
            # drop it and retry (caching just doesn't engage, never an error).
            if "prompt_cache_key" in message and "prompt_cache_key" in retry_kwargs:
                retry_kwargs.pop("prompt_cache_key", None)
                changed = True
            if not changed:
                raise
            response = self._create_with_rate_limit_retry(client, retry_kwargs)
        usage = getattr(response, "usage", None)
        if usage is not None:
            details = getattr(usage, "prompt_tokens_details", None)
            cached = getattr(details, "cached_tokens", 0) or 0 if details is not None else 0
            self.usage.record(
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                cached_prompt_tokens=cached,
            )
        return response.choices[0].message.content or ""


class ScriptedLLMClient:
    """Test/demo double: returns canned responses in order, one per call."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []
        # Present for interface parity with the real clients (orchestrator
        # reads `getattr(client, "usage", None)` when totaling a batch's
        # token spend); scripted/mocked runs never spend real tokens.
        self.usage = TokenUsage()

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
