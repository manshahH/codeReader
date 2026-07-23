"""npm audit gate with a time-boxed, per-advisory acknowledgement (D-154).

`npm audit --audit-level=high` fails on ANY high/critical advisory. That is the
right strictness, but it made the dependency-audit job PERMANENTLY red on two
build-tool advisories that do not affect shipped output (vite dev-server, a
build-time transitive), and a permanently-red job is exactly what let the
18-day-dead pytest job go unnoticed (D-150/D-152). A blanket suppression is not
the answer either -- it would also hide a NEW advisory.

So this gate tolerates ONLY the specific advisory IDs listed in
npm_audit_allowlist.json, and ONLY until that file's `expires` date. It fails
(red) on: any high/critical advisory NOT on the list, OR any time the list has
expired. A new advisory still turns the job red; the acknowledgement cannot
become permanent by inattention, because the date makes it expire loudly.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

_ALLOWLIST = Path(__file__).resolve().parent / "npm_audit_allowlist.json"
_BLOCKING_SEVERITIES = {"high", "critical"}


def high_advisory_ids(audit_json: dict) -> set[str]:
    """The GHSA ids of every high/critical advisory in `npm audit --json`
    output. npm nests the advisory url (which carries the GHSA id) under each
    vulnerability's `via` entries; only dict vias are real advisories, string
    vias are just package-name back-references."""
    ids: set[str] = set()
    for vuln in audit_json.get("vulnerabilities", {}).values():
        for via in vuln.get("via", []):
            if not isinstance(via, dict):
                continue
            if via.get("severity") not in _BLOCKING_SEVERITIES:
                continue
            url = via.get("url", "")
            ghsa = url.rstrip("/").split("/")[-1]
            if ghsa.startswith("GHSA-"):
                ids.add(ghsa)
    return ids


def evaluate(high_ids: set[str], allowlist: dict, today: dt.date) -> tuple[bool, str]:
    """Pure decision. GREEN only when every high/critical advisory is
    explicitly acknowledged AND the acknowledgement has not expired."""
    expires = dt.date.fromisoformat(allowlist["expires"])
    acknowledged = set(allowlist.get("advisories", {}))

    if today > expires:
        return False, (
            f"npm-audit acknowledgement EXPIRED on {expires} (today {today}). "
            f"Re-review the tolerated advisories and either fix them or set a new "
            f"expiry in scripts/npm_audit_allowlist.json. Tolerated: "
            f"{sorted(acknowledged)}."
        )

    unacknowledged = sorted(high_ids - acknowledged)
    if unacknowledged:
        return False, (
            f"NEW high/critical npm advisory not acknowledged: {unacknowledged}. "
            f"This is a real finding -- fix it, or (if it is out of the shipped "
            f"path and deferred) add it to scripts/npm_audit_allowlist.json with a "
            f"reason and it will be tolerated until {expires}."
        )

    tolerated = sorted(high_ids & acknowledged)
    return True, (
        f"npm audit clean except {len(tolerated)} acknowledged advisory(ies), "
        f"tolerated until {expires}: {tolerated}. A NEW advisory would still fail."
    )


def main() -> int:
    allowlist = json.loads(_ALLOWLIST.read_text(encoding="utf-8"))
    # npm audit exits non-zero when vulns exist; we want its JSON regardless.
    proc = subprocess.run(
        ["npm", "audit", "--json"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent / "frontend",
        shell=sys.platform == "win32",
    )
    try:
        audit_json = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(f"could not parse `npm audit --json` output:\n{proc.stdout}\n{proc.stderr}")
        return 1

    ok, message = evaluate(high_advisory_ids(audit_json), allowlist, dt.date.today())
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
