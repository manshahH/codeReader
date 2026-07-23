"""The npm-audit tolerance gate's decision logic (D-154).

The gate lets the dependency-audit job go green on specifically-acknowledged,
time-boxed advisories while still failing on anything new or on expiry. These
tests pin that logic so it can never quietly become a blanket suppression."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from scripts.npm_audit_gate import evaluate, high_advisory_ids

_ALLOWLIST_PATH = Path(__file__).resolve().parents[2] / "scripts" / "npm_audit_allowlist.json"

# A trimmed `npm audit --json` shape: one HIGH advisory, one MODERATE.
_AUDIT = {
    "vulnerabilities": {
        "vite": {
            "severity": "high",
            "via": [
                {"severity": "high", "url": "https://github.com/advisories/GHSA-fx2h-pf6j-xcff"},
                {"severity": "moderate", "url": "https://github.com/advisories/GHSA-4w7w-66w2-5vf9"},
                "esbuild",  # a string via -- a package back-reference, not an advisory
            ],
        },
        "left-pad": {
            "severity": "moderate",
            "via": [
                {"severity": "moderate", "url": "https://github.com/advisories/GHSA-moderate-only"},
            ],
        },
    }
}


def test_only_high_and_critical_ghsa_ids_are_extracted() -> None:
    ids = high_advisory_ids(_AUDIT)
    assert ids == {"GHSA-fx2h-pf6j-xcff"}  # the moderate via and the string via are excluded


def test_gate_is_green_when_every_high_is_acknowledged_and_unexpired() -> None:
    allowlist = {"expires": "2026-09-15", "advisories": {"GHSA-fx2h-pf6j-xcff": "vite dev-server"}}
    ok, msg = evaluate({"GHSA-fx2h-pf6j-xcff"}, allowlist, dt.date(2026, 7, 24))
    assert ok is True
    assert "GHSA-fx2h-pf6j-xcff" in msg


def test_gate_is_RED_on_a_new_unacknowledged_high() -> None:
    """Negative (house rule): a HIGH advisory not on the list must fail, so a
    real new finding is never swallowed by the tolerance."""
    allowlist = {"expires": "2026-09-15", "advisories": {"GHSA-fx2h-pf6j-xcff": "vite"}}
    high = {"GHSA-fx2h-pf6j-xcff", "GHSA-brand-new-xxxx"}
    ok, msg = evaluate(high, allowlist, dt.date(2026, 7, 24))
    assert ok is False
    assert "GHSA-brand-new-xxxx" in msg


def test_gate_is_RED_once_the_acknowledgement_has_expired() -> None:
    """Negative (house rule): past the expiry the gate fails even on the very
    advisories it used to tolerate -- the deferral cannot become permanent."""
    allowlist = {"expires": "2026-09-15", "advisories": {"GHSA-fx2h-pf6j-xcff": "vite"}}
    ok, msg = evaluate({"GHSA-fx2h-pf6j-xcff"}, allowlist, dt.date(2026, 9, 16))
    assert ok is False
    assert "EXPIRED" in msg


def test_the_real_allowlist_is_wellformed_and_not_already_expired() -> None:
    """The committed allowlist must parse and must not ship already-expired, or
    CI would be red on arrival for the wrong reason."""
    allowlist = json.loads(_ALLOWLIST_PATH.read_text(encoding="utf-8"))
    expires = dt.date.fromisoformat(allowlist["expires"])
    assert allowlist["advisories"], "allowlist must name the specific advisories, never be empty"
    assert expires > dt.date(2026, 7, 24), "the committed acknowledgement must not ship expired"
