"""Versioned concept taxonomy (docs/01-content-spec.md).

Controlled, versioned vocabulary driving the spec sampler, spaced repetition,
and future skill graph. Stamped onto every exercise as `concepts` plus this
module's TAXONOMY_VERSION, so a taxonomy edit never silently reinterprets an
already-shipped exercise's tags.
"""

from __future__ import annotations

import dataclasses

TAXONOMY_VERSION = "v1"

_BOTH = frozenset({"spot_the_bug", "trace"})
_STB_ONLY = frozenset({"spot_the_bug"})
_TRACE_ONLY = frozenset({"trace"})


@dataclasses.dataclass(frozen=True)
class Concept:
    slug: str
    name: str
    category: str
    applies_to: frozenset[str]
    # D-54: names the forbidden construct this concept cannot be written
    # without (per static_gate + generator prompt constraint 2). A flagged
    # concept is never sampled -- every one of its specs burned a full
    # generate+gate round by construction. Flagged, not deleted: a future
    # narrow allowance (e.g. permitting open() for the resource-leak concept
    # specifically) re-enables it by clearing this field.
    requires_forbidden: str | None = None
    # D-80: names why this concept's canonical spot_the_bug realization cannot
    # yield a valid twin-snippet with a diff-derived answer key, so it is
    # excluded from spot_the_bug (and, transitively, predict_the_fix -- which
    # is derived from verified spot_the_bug candidates) while remaining valid
    # for trace where it applies. Two structural failure modes, both proven
    # 100%-deterministic in the reject reports: (a) OMISSION bugs, whose fix is
    # a pure INSERTION (a missing @wraps, a missing idempotency guard) -- D-49
    # correctly rejects the empty diff (nothing for the exercise to point at);
    # (b) NO-DIVERGENCE bugs, where buggy and fixed produce identical output so
    # no test can discriminate them (a conceptual race with no real threads, an
    # N+1 whose only difference is a side-effect count). This is the same class
    # as D-54 (the gate is right, the concept/type pairing is wrong); per-type,
    # not global, precisely because these often remain fine for trace. Flagged,
    # not deleted: get_concept still resolves the slug for already-published
    # exercises, and a future STB realization that dodges the failure mode
    # re-enables it by clearing this field.
    stb_unsamplable: str | None = None


CONCEPTS: tuple[Concept, ...] = (
    Concept("mutable-default-arg", "Mutable default argument", "mutable-state", _BOTH),
    Concept("aliasing-vs-copy", "Aliasing vs. copying", "mutable-state", _BOTH),
    Concept("shallow-vs-deep-copy", "Shallow vs. deep copy", "mutable-state", _BOTH),
    Concept("shared-class-attribute", "Shared mutable class attribute", "mutable-state", _BOTH),
    Concept(
        "dict-mutation-during-iteration",
        "Mutating a dict while iterating it",
        "mutable-state",
        _BOTH,
    ),
    Concept(
        "list-mutation-during-iteration",
        "Mutating a list while iterating it",
        "mutable-state",
        _BOTH,
    ),
    Concept("closure-late-binding", "Closure late-binding capture", "scoping", _BOTH),
    Concept("global-state-mutation", "Hidden global state mutation", "scoping", _BOTH),
    Concept("variable-shadowing", "Variable shadowing", "scoping", _BOTH),
    Concept("walrus-scope", "Walrus operator scope leakage", "scoping", _BOTH),
    Concept("off-by-one", "Off-by-one loop/index error", "control-flow", _BOTH),
    Concept("off-by-one-slicing", "Off-by-one in slicing", "control-flow", _BOTH),
    Concept(
        "early-return-skipped-path",
        "Early return skips a later code path",
        "control-flow",
        _TRACE_ONLY,
    ),
    Concept("exception-swallowing", "Overly broad exception swallowing", "error-handling", _BOTH),
    Concept(
        "exception-type-too-broad",
        "Catching a broader exception type than intended",
        "error-handling",
        _BOTH,
        stb_unsamplable=(
            "the canonical fix narrows an over-broad except by ADDING a "
            "specific handler / re-raise (a pure insertion, D-49 rejects the "
            "empty diff); confirmed 100%-deterministic sandbox reject. Still "
            "valid for trace (what does the broad catch print?)"
        ),
    ),
    Concept(
        "resource-leak-unclosed-file",
        "Unclosed file handle / resource leak",
        "resources",
        _STB_ONLY,
        requires_forbidden=(
            "open()/file I/O (static_gate FORBIDDEN_CALL_NAMES + prompt constraint 2)"
        ),
    ),
    Concept("context-manager-misuse", "Context manager used incorrectly", "resources", _BOTH),
    Concept(
        "generator-exhaustion",
        "Generator/iterator exhausted after first use",
        "iteration",
        _BOTH,
    ),
    Concept(
        "sorting-stability-assumption",
        "Wrong assumption about sort stability",
        "iteration",
        _BOTH,
    ),
    Concept("key-function-misuse", "sorted()/min()/max() key function misuse", "iteration", _BOTH),
    Concept("integer-division-truncation", "Integer division truncation", "numeric", _BOTH),
    Concept("float-precision", "Floating point precision surprise", "numeric", _BOTH),
    Concept(
        "string-formatting-mismatch",
        "String formatting / f-string mismatch",
        "strings",
        _BOTH,
    ),
    Concept("string-immutability-misuse", "Treating strings as mutable", "strings", _BOTH),
    Concept("string-vs-bytes-confusion", "str/bytes confusion", "strings", _BOTH),
    Concept(
        "encoding-decoding-mismatch",
        "Encoding/decoding mismatch",
        "strings",
        _STB_ONLY,
    ),
    Concept(
        "timezone-naive-vs-aware",
        "Naive vs. timezone-aware datetimes",
        "time-and-io",
        _STB_ONLY,
    ),
    Concept(
        "boolean-short-circuit-side-effect",
        "Short-circuit evaluation hides a side effect",
        "control-flow",
        _BOTH,
    ),
    Concept(
        "truthy-falsy-empty-check",
        "Truthy/falsy check on the wrong empty value",
        "control-flow",
        _BOTH,
    ),
    Concept("is-vs-equality", "`is` used where `==` was intended", "control-flow", _BOTH),
    Concept(
        "decorator-losing-metadata",
        "Decorator loses function metadata/behavior",
        "functions",
        _STB_ONLY,
        stb_unsamplable=(
            "omission bug: the fix INSERTS @functools.wraps(func) on the "
            "wrapper -- a pure insertion, so the diff-derived key is empty and "
            "D-49 rejects it. Confirmed 3/3 deterministic reject"
        ),
    ),
    Concept(
        "recursion-missing-base-case",
        "Recursion missing/incorrect base case",
        "functions",
        _BOTH,
    ),
    Concept(
        "memoization-cache-staleness",
        "Stale memoization cache across calls",
        "functions",
        _STB_ONLY,
    ),
    Concept(
        "dataclass-mutable-default",
        "Dataclass field with a mutable default",
        "oop",
        _STB_ONLY,
    ),
    Concept(
        "unpacking-order-assumption",
        "Wrong assumption about unpacking order",
        "control-flow",
        _TRACE_ONLY,
    ),
    Concept(
        "n-plus-one-pattern",
        "N+1 query pattern (conceptual)",
        "performance",
        _STB_ONLY,
        stb_unsamplable=(
            "no-divergence bug: batching an N+1 changes only a side-effect "
            "count (queries issued), not the returned value, so buggy and "
            "fixed produce identical output and no twin-snippet test can "
            "discriminate them; the fix is also a whole-loop restructure, not "
            "a minimal diff"
        ),
    ),
    Concept(
        "retry-without-backoff",
        "Retry logic without backoff/limit (conceptual)",
        "reliability",
        _STB_ONLY,
        requires_forbidden=(
            "time/time.sleep for backoff (FORBIDDEN_IMPORTS); and an unbounded "
            "retry can only fail by sandbox timeout, never AssertionError"
        ),
    ),
    Concept(
        "idempotency-missing",
        "Missing idempotency guard (conceptual)",
        "reliability",
        _STB_ONLY,
        stb_unsamplable=(
            "omission bug: the fix INSERTS a guard clause (if key in seen: "
            "return) -- a pure insertion with an empty diff, rejected by D-49. "
            "Confirmed 3/3 deterministic reject"
        ),
    ),
    Concept(
        "injection-string-concat",
        "Building a query/command by string concatenation (conceptual)",
        "security",
        _STB_ONLY,
    ),
    Concept(
        "concurrency-conceptual",
        "Shared-state race condition (conceptual, no real threads)",
        "concurrency",
        _STB_ONLY,
        stb_unsamplable=(
            "no-divergence AND omission: with threading forbidden the race "
            "never triggers in deterministic single-threaded execution (buggy "
            "and fixed print the same thing), and the conceptual fix is an "
            "INSERTED lock/guard; no discriminating twin-snippet exists"
        ),
    ),
)

if len({c.slug for c in CONCEPTS}) != len(CONCEPTS):
    raise ValueError("pipeline.taxonomy.CONCEPTS contains duplicate slugs")


def concepts_for_type(exercise_type: str) -> tuple[Concept, ...]:
    """Samplable concepts only, so the spec sampler never burns a generate+gate
    round on a spec that cannot yield. Two exclusions:

    * requires_forbidden (D-54): the concept's natural vehicle is a forbidden
      construct, for every type it applies to.
    * stb_unsamplable (D-80): the concept's canonical spot_the_bug bug cannot
      produce a discriminating twin-snippet with a diff-derived key (an
      omission bug or a no-output-divergence bug). This one is spot_the_bug-
      specific -- the concept usually stays valid for trace -- and covers
      predict_the_fix transitively, since predict_the_fix candidates are
      derived from verified spot_the_bug candidates, never sampled directly.
    """
    return tuple(
        c
        for c in CONCEPTS
        if exercise_type in c.applies_to
        and c.requires_forbidden is None
        and not (exercise_type == "spot_the_bug" and c.stb_unsamplable is not None)
    )


def get_concept(slug: str) -> Concept:
    for concept in CONCEPTS:
        if concept.slug == slug:
            return concept
    raise KeyError(slug)
