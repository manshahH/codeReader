"""M5: hand-authored, human-verified summarize exercises for local/manual
testing of the end-to-end inline rubric grading loop.

The pipeline (M3) generates spot_the_bug and trace only; it does not
generate summarize yet (out of scope for M5, noted as a seam for the future
generator). These three are hand-authored to unblock M5 testing.

Marked `source.origin="seed_handauthored"` (never "llm"/"oss_bug"/etc, see
docs/01 section on `source`) precisely so M8's 200-exercise content-count and
taxonomy-coverage logic can filter non-pipeline origins out and nobody
mistakes these three for representative launch content.

Idempotent: fixed UUIDs (uuid5, deterministic from a name), so re-running
this script is a no-op past the first run (skips any (id, version) already
present) rather than accumulating duplicates.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.db import create_engine, create_session_factory  # noqa: E402
from app.models import Exercise  # noqa: E402

# Fixed, arbitrary namespace UUID (RFC 4122 uuid5) so re-running this script
# always derives the same exercise ids -- that's what makes it idempotent.
_SEED_NAMESPACE = uuid.UUID("c0debee5-0000-4000-8000-000000000005")


def _seed_id(name: str) -> uuid.UUID:
    return uuid.uuid5(_SEED_NAMESPACE, name)


RETRY_CODE = (
    "import time\n\n"
    "def call_with_retry(func, max_attempts=3, backoff_base=0.5):\n"
    "    attempt = 0\n"
    "    while True:\n"
    "        try:\n"
    "            return func()\n"
    "        except (ConnectionError, TimeoutError):\n"
    "            attempt += 1\n"
    "            if attempt >= max_attempts:\n"
    "                raise\n"
    "            time.sleep(backoff_base * (2 ** attempt))\n"
)

TTL_CACHE_CODE = (
    "import time\n\n"
    "class TTLCache:\n"
    "    def __init__(self, ttl_seconds):\n"
    "        self._ttl = ttl_seconds\n"
    "        self._store = {}\n\n"
    "    def get(self, key):\n"
    "        entry = self._store.get(key)\n"
    "        if entry is None:\n"
    "            return None\n"
    "        value, expires_at = entry\n"
    "        if time.time() >= expires_at:\n"
    "            del self._store[key]\n"
    "            return None\n"
    "        return value\n\n"
    "    def set(self, key, value):\n"
    "        self._store[key] = (value, time.time() + self._ttl)\n"
)

CIRCUIT_BREAKER_CODE = (
    "import time\n\n"
    "class CircuitBreaker:\n"
    "    def __init__(self, failure_threshold=3, reset_timeout=30):\n"
    "        self._threshold = failure_threshold\n"
    "        self._reset_timeout = reset_timeout\n"
    "        self._failures = 0\n"
    "        self._opened_at = None\n\n"
    "    def call(self, func):\n"
    "        if self._opened_at is not None:\n"
    "            if time.time() - self._opened_at < self._reset_timeout:\n"
    "                raise RuntimeError('circuit open')\n"
    "            self._opened_at = None\n"
    "            self._failures = 0\n"
    "        try:\n"
    "            result = func()\n"
    "        except Exception:\n"
    "            self._failures += 1\n"
    "            if self._failures >= self._threshold:\n"
    "                self._opened_at = time.time()\n"
    "            raise\n"
    "        else:\n"
    "            self._failures = 0\n"
    "            return result\n"
)

EXERCISES = [
    dict(
        id=_seed_id("summarize-retry-with-backoff-v1"),
        version=1,
        language="python",
        type="summarize",
        grading_mode="rubric",
        difficulty_authored=5,
        concepts=["retry-without-backoff"],
        tags=["seed"],
        status="live",
        source={"origin": "seed_handauthored", "attribution": "hand-authored for M5"},
        payload={
            "code": RETRY_CODE,
            "context_note": "A helper used to call flaky network functions.",
            "max_words": 60,
        },
        grading={
            "mode": "rubric",
            "rubric": {
                "must_mention": [
                    {"point": "retries the wrapped call with exponential backoff", "weight": 0.4},
                    {"point": "only retries network-related errors", "weight": 0.3},
                    {
                        "point": "re-raises the original exception after the final attempt",
                        "weight": 0.3,
                    },
                ],
                "must_not_claim": ["retries forever with no limit", "retries on any exception"],
                "pass_threshold": 0.6,
            },
            "reference_answer": (
                "Retries the wrapped call up to max_attempts times with exponential "
                "backoff, but only for ConnectionError/TimeoutError, then re-raises "
                "the original exception once the attempt count is exhausted."
            ),
        },
        explanation={
            "summary": "A retry wrapper with backoff, scoped to network errors.",
            "principle": "Retries should be bounded and scoped to transient failures.",
        },
        est_time_s=90,
        human_reviewed=True,
    ),
    dict(
        id=_seed_id("summarize-ttl-cache-v1"),
        version=1,
        language="python",
        type="summarize",
        grading_mode="rubric",
        difficulty_authored=5,
        concepts=["memoization-cache-staleness"],
        tags=["seed"],
        status="live",
        source={"origin": "seed_handauthored", "attribution": "hand-authored for M5"},
        payload={
            "code": TTL_CACHE_CODE,
            "context_note": "A small in-memory cache with expiring entries.",
            "max_words": 60,
        },
        grading={
            "mode": "rubric",
            "rubric": {
                "must_mention": [
                    {"point": "caches values with an expiry time (TTL)", "weight": 0.4},
                    {
                        "point": "get() evicts and returns None once the entry has expired",
                        "weight": 0.35,
                    },
                    {
                        "point": "set() stores the value alongside its expiry timestamp",
                        "weight": 0.25,
                    },
                ],
                "must_not_claim": [
                    "uses an LRU eviction policy",
                    "is safe for concurrent/threaded access",
                ],
                "pass_threshold": 0.6,
            },
            "reference_answer": (
                "A cache that stores each value with an expiry timestamp; get() "
                "returns the value if it hasn't expired yet, evicting and returning "
                "None once the TTL has passed, and set() records a fresh expiry "
                "each time a key is written."
            ),
        },
        explanation={
            "summary": "A TTL cache that lazily evicts expired entries on read.",
            "principle": "Expiry is checked lazily, on access, not by a background sweep.",
        },
        est_time_s=90,
        human_reviewed=True,
    ),
    dict(
        id=_seed_id("summarize-circuit-breaker-v1"),
        version=1,
        language="python",
        type="summarize",
        grading_mode="rubric",
        difficulty_authored=6,
        concepts=["exception-type-too-broad"],
        tags=["seed"],
        status="live",
        source={"origin": "seed_handauthored", "attribution": "hand-authored for M5"},
        payload={
            "code": CIRCUIT_BREAKER_CODE,
            "context_note": "Wraps calls to an unreliable downstream dependency.",
            "max_words": 60,
        },
        grading={
            "mode": "rubric",
            "rubric": {
                "must_mention": [
                    {
                        "point": "trips open after failure_threshold consecutive failures",
                        "weight": 0.4,
                    },
                    {"point": "rejects calls immediately while the circuit is open", "weight": 0.3},
                    {
                        "point": "stays open for reset_timeout seconds before allowing a retry",
                        "weight": 0.3,
                    },
                ],
                "must_not_claim": [
                    "retries the failed call automatically",
                    "permanently disables the function",
                ],
                "pass_threshold": 0.6,
            },
            "reference_answer": (
                "Tracks consecutive failures and, once failure_threshold is reached, "
                "opens the circuit so further calls are rejected immediately without "
                "even attempting func(). After reset_timeout seconds it allows one "
                "call through again, closing the circuit on success."
            ),
        },
        explanation={
            "summary": "A circuit breaker that fails fast once a downstream call is unreliable.",
            "principle": "Fail fast and back off, rather than retrying a call that keeps failing.",
        },
        est_time_s=100,
        human_reviewed=True,
    ),
]


async def main() -> None:
    engine = create_engine()
    session_factory = create_session_factory(engine)
    inserted = 0
    async with session_factory() as session:
        for spec in EXERCISES:
            existing = await session.get(Exercise, (spec["id"], spec["version"]))
            if existing is not None:
                continue
            session.add(Exercise(**spec))
            inserted += 1
        await session.commit()
    await engine.dispose()
    print(f"seed_summarize_exercises: inserted {inserted} of {len(EXERCISES)} exercises")


if __name__ == "__main__":
    asyncio.run(main())
