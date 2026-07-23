"""The one place that knows which plan a feature belongs to (D-145).

WHY core/ AND NOT A DOMAIN PACKAGE (D-145(a)): this is cross-cutting
infrastructure with no models and no router, exactly like core/ratelimit.py and
core/idempotency.py. The module law is routers -> services -> models, with
cross-domain calls going through services; a domain that had to ask "is this
user entitled to feature X" would otherwise import another domain's service to
get a yes/no. core/ is the layer every domain may already import, so the gate
lives here and nobody reaches across domains for it.

WHY SYNCHRONOUS AND WHY IT TAKES THE ALREADY-LOADED User (D-145(a), (c)): a
check that CAN do I/O eventually WILL, once per request in a loop. resolve_plan
returns a constant today and reads the User row's future `plan` column when one
lands; taking `User` (not `user_id`) keeps the signature stable across that
change AND means a call site adds ZERO queries, because every gated endpoint
already loads its User row (measured: GET /v1/session/today issues exactly one
`SELECT ... FROM users`, D-145 item 1). Callers holding only a CurrentUser load
the row explicitly, as almost all of them already do.

THE FAILURE MODE THIS IS DESIGNED AGAINST (D-145(a)): `if user.is_pro`
scattered across routers. Flipping a feature then means finding every site, and
missing one is a silent leak rather than a loud error. One function, one module,
one grep.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from app.core.errors import ApiError

if TYPE_CHECKING:
    # Type-only: the gate is pure and never touches a User attribute at runtime
    # (resolve_plan returns a constant). Keeping this out of the runtime import
    # graph is deliberate -- core/ stays free of a hard dependency on the models
    # package, and there is no import cycle to reason about.
    from app.models import User


class Plan(StrEnum):
    """The tiers that can exist. Only FREE is reachable today (D-145 decision 2:
    no billing, no plan storage). Paid tiers are added here when billing lands;
    adding one is a code change to this module and nowhere else."""

    FREE = "free"


class Feature(StrEnum):
    """THE REGISTRY (D-145(b)). A key must be declared here before it can be
    gated, which is what makes the CI coverage check in
    test_entitlements_registry.py possible at all.

    NAMING (D-145(b), enforced socially, not mechanically):
      (i)   NEVER a tier name in the key. `pro_cheat_sheet` is banned: the name
            goes stale the instant the map moves it, and a stale name is how the
            paid knowledge leaks back out of the map.
      (ii)  A key is stable FOREVER. It appears in feature_usage rows and in any
            future billing config, so renaming one orphans history.
      (iii) ONE KEY PER INDEPENDENTLY FLIPPABLE UNIT. Forced by decision (4),
            not taste: export must stay free when the sheet goes paid, so
            `cheat_sheet` and `cheat_sheet_export` are two keys from day one.

    These two are registered ahead of A5 so EXPORT_OF and the flip guard have
    something concrete to constrain. Both are FREE today (see PLAN_FEATURES)."""

    CHEAT_SHEET = "cheat_sheet"
    CHEAT_SHEET_EXPORT = "cheat_sheet_export"


# THE PLAN-TO-FEATURE MAP IS DATA (D-145(b)). This dict is the ONLY place that
# knows which tier a feature belongs to. Today it is literally "free gets every
# registered feature", so the gate answers yes for everything and decision (2)
# holds with no special-casing. Flipping the cheat sheet to paid is then
# removing one key from the free set and putting it in a paid set: a change to
# THIS dict, with zero edits to cheat-sheet code. If a feature's own module ever
# contains the knowledge that it is paid, the design has failed, and the
# map_change_alone_flips_it test is what proves it has not.
PLAN_FEATURES: dict[Plan, frozenset[Feature]] = {
    Plan.FREE: frozenset(Feature),
}


# EXPORT IS A PRECONDITION, NOT A FOLLOW-UP (D-145(e)). Maps a gated-capable
# feature to the export key that must ship free BEFORE it may move to a paid
# tier. The flip guard (test_entitlements.py) asserts every gated feature has an
# export key here and that the export key is in the free set, so a flip that
# forgets export fails CI rather than shipping and stranding a user's work.
EXPORT_OF: dict[Feature, Feature] = {
    Feature.CHEAT_SHEET: Feature.CHEAT_SHEET_EXPORT,
}


def resolve_plan(user: User) -> Plan:  # noqa: ARG001 -- see D-145(c)
    """The single billing seam (D-145(c)).

    Hardcoded FREE, no column, no migration. A `users.plan` column that nothing
    can write anything but its default into is not data, it is a default with a
    storage cost and a drift risk; and when billing arrives the payment provider
    is the source of truth, so the column becomes a PROJECTION of webhook events
    with its own sync/backfill/reconciliation semantics -- designed once, with
    the code that writes it, not now. The JWT `plan` claim is NOT this source and
    must not become it (a 15-minute token would delay a downgrade or refund; see
    D-145(c) and the vestigial-claim notes at auth/tokens.py and docs/05)."""

    return Plan.FREE


def is_entitled(user: User, feature: Feature) -> bool:
    """Yes/no, for the rare branch that SHAPES a response rather than refusing
    it. Most call sites want require_entitled instead."""

    return feature in PLAN_FEATURES[resolve_plan(user)]


def require_entitled(user: User, feature: Feature) -> None:
    """The gate. Call it as the FIRST statement of the SERVICE function that
    produces the gated resource (D-145(d) shape 1): a router dependency protects
    one path, but the module law makes the service the shared choke point every
    present and future caller passes through.

    Raises 403 feature_not_entitled and returns nothing on success."""

    if not is_entitled(user, feature):
        raise ApiError(
            403,
            "feature_not_entitled",
            "This feature is not available on your plan.",
        )
