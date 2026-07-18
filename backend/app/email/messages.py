"""The verification email itself (A2, D-120).

Voice per docs/08: specific, not cheerful, no guilt. It says what the address is
for, because "add email for reminders and your weekly recap" is the promise the
capture prompt made and the email has to keep it.

The link is built from settings.APP_ORIGIN and NEVER from a request header.
Host, X-Forwarded-Host and friends are attacker-controlled, and a verification
link is exactly the thing worth pointing at an attacker's origin: the victim
clicks a legitimate-looking mail from us and hands their token away.
"""

from __future__ import annotations

from urllib.parse import quote

from app.config import get_settings
from app.email.sender import OutboundEmail

SUBJECT = "Confirm your email for CodeReader"


def verification_link(token: str) -> str:
    origin = get_settings().APP_ORIGIN.rstrip("/")
    return f"{origin}/verify-email?token={quote(token, safe='')}"


def build_verification_email(*, to: str, token: str, ttl_hours: int) -> OutboundEmail:
    link = verification_link(token)
    hours = f"{ttl_hours} hours" if ttl_hours != 1 else "1 hour"
    text = (
        "Confirm this address to turn on CodeReader reminders and your weekly recap.\n\n"
        f"{link}\n\n"
        f"The link works for {hours}. Until you confirm, nothing changes: if you "
        "already had an address on file, it keeps working.\n\n"
        "If you did not ask for this, ignore it. No address is added unless the "
        "link is opened.\n"
    )
    html = (
        "<p>Confirm this address to turn on CodeReader reminders and your weekly recap.</p>"
        f'<p><a href="{link}">Confirm this address</a></p>'
        f"<p>The link works for {hours}. Until you confirm, nothing changes: if you "
        "already had an address on file, it keeps working.</p>"
        "<p>If you did not ask for this, ignore it. No address is added unless the "
        "link is opened.</p>"
    )
    return OutboundEmail(to=to, subject=SUBJECT, text=text, html=html, dev_link=link)
