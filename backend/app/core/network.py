"""Client IP resolution behind an optional trusted reverse proxy.

X-Forwarded-For is `client, proxy1, proxy2, ...`: each hop APPENDS the peer
address it received the connection from onto the right end. Trusting the
LEFTMOST entry (the naive `split(",")[0]`) lets any client set an arbitrary
value there themselves -- an attacker rotating that header defeats any
per-IP limit keyed on it. The rightmost `trusted_proxy_count` entries were
appended by infrastructure we control, not the client, so counting in from
the right is the only spoof-resistant read. docs/03's MVP topology is one LB
in front of the API instances, hence the default of 1.
"""

from __future__ import annotations

from fastapi import Request


def resolve_client_ip(request: Request, trusted_proxy_count: int) -> str:
    direct_peer = request.client.host if request.client else "unknown"
    if trusted_proxy_count <= 0:
        return direct_peer

    forwarded_for = request.headers.get("x-forwarded-for")
    if not forwarded_for:
        return direct_peer

    hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    if len(hops) < trusted_proxy_count:
        # Fewer hops than we trust: the header is short/tampered. Falling
        # back to the direct TCP peer is safe -- it can't be spoofed via
        # headers, only refuses to give the "real" client IP behind a proxy.
        return direct_peer
    return hops[-trusted_proxy_count]
