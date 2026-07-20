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

import uuid
from urllib.parse import quote

from app.config import get_settings
from app.email.recap import WeeklyRecap
from app.email.sender import OutboundEmail
from app.email.unsubscribe import unsubscribe_api_url, unsubscribe_page_url

SUBJECT = "Confirm your email for CodeReader"


# A3 (D-137(9)). docs/10's two hard rules for this audience are no guilt and no
# streak-loss threat, and an email is the easiest place to break both, because
# it is written once and then sent to everyone forever without anyone reading it
# again. A1 deliberately replaced the streak-reset path with a welcome-back
# state; a reminder that leans on losing the streak would put the exact thing A1
# removed back into the product, out of sight, in the user's inbox.
#
# So these phrases are banned in the two templates below, and a test greps for
# them. The list is the failure mode, not a style preference.
BANNED_REMINDER_PHRASES = (
    "don't lose",
    "dont lose",
    "you'll lose",
    "youll lose",
    "will lose",
    "about to lose",
    "your streak ends",
    "streak is at risk",
    "last chance",
    "still time",
    "hurry",
    "before it's too late",
    "keep it alive",
    "!",
)


def verification_link(token: str) -> str:
    origin = get_settings().PRIMARY_APP_ORIGIN
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


def _unsubscribe_headers(user_id: uuid.UUID, kind: str) -> dict[str, str]:
    """RFC 8058 one-click. Both headers or neither (D-137(7)).

    List-Unsubscribe-Post without a URL to POST to is meaningless, and the URL
    without the Post header only earns a mail client's unsubscribe affordance in
    some clients. The mailto is the fallback for clients that will not POST, and
    it is derived from EMAIL_FROM rather than being a separate setting, so it
    cannot drift away from the domain we actually send from.
    """
    settings = get_settings()
    from_address = settings.EMAIL_FROM
    if "<" in from_address:
        from_address = from_address.split("<", 1)[1].split(">", 1)[0]
    return {
        "List-Unsubscribe": (
            f"<{unsubscribe_api_url(user_id, kind)}>, "
            f"<mailto:{from_address}?subject=unsubscribe-{kind}>"
        ),
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def _footer(link: str, what: str) -> tuple[str, str]:
    text = (
        f"\n\nYou get this because you added your address to CodeReader.\n"
        f"Turn off {what}: {link}\n"
    )
    html = (
        "<hr><p>You get this because you added your address to CodeReader. "
        f'<a href="{link}">Turn off {what}</a>.</p>'
    )
    return text, html


def build_reminder_email(
    *, to: str, user_id: uuid.UUID, exercise_count: int | None = None
) -> OutboundEmail:
    """The daily reminder.

    Says what is waiting, and stops. It does not mention the streak at all --
    not to protect it, not to threaten it, not to celebrate it. The streak is a
    thing the user sees in the app when they arrive; using it as leverage in a
    push channel is exactly the emotional engine docs/10 rules out. No count of
    days missed, no scarcity, no exclamation mark.

    `exercise_count` is None when today's session has not been built yet, which
    is the common case for a user who has not opened the app -- exactly the user
    this mail is going to. The count is then simply omitted rather than guessed:
    session length varies (sampler.MIN_SLOTS and up), and the job must not build
    a session as a side effect of reminding someone one exists.
    """
    link = unsubscribe_page_url(user_id, "reminder")
    origin = get_settings().PRIMARY_APP_ORIGIN
    footer_text, footer_html = _footer(link, "reminders")

    if exercise_count is None:
        headline = "Today's session is ready."
    elif exercise_count == 1:
        headline = "Today's session is ready: one exercise to read."
    else:
        headline = f"Today's session is ready: {exercise_count} exercises to read."

    text = (
        f"{headline}\n\n"
        f"{origin}/session\n\n"
        "Five to ten minutes, whenever it suits you."
        f"{footer_text}"
    )
    html = (
        f"<p>{headline}</p>"
        f'<p><a href="{origin}/session">Open today\'s session</a></p>'
        "<p>Five to ten minutes, whenever it suits you.</p>"
        f"{footer_html}"
    )
    return OutboundEmail(
        to=to,
        subject="Your CodeReader session is ready",
        text=text,
        html=html,
        dev_link=link,
        headers=_unsubscribe_headers(user_id, "reminder"),
    )


def build_recap_email(*, to: str, user_id: uuid.UUID, recap: WeeklyRecap) -> OutboundEmail:
    """The weekly recap: what happened, stated plainly.

    Reports, does not evaluate. There is no "you could have done better" and no
    target the reader failed to hit, because the week they had is the only week
    there is to report. An empty week never reaches this function at all
    (D-137(8)) -- the job skips it, so there is no "you did nothing" template to
    get the tone wrong in.
    """
    link = unsubscribe_page_url(user_id, "recap")
    origin = get_settings().PRIMARY_APP_ORIGIN
    span = f"{recap.week_start.isoformat()} to {recap.week_end.isoformat()}"
    footer_text, footer_html = _footer(link, "the weekly recap")

    lines = [
        f"Sessions completed: {recap.sessions_completed}",
        f"Exercises read: {recap.exercises_attempted}",
    ]
    if recap.accuracy_pct is not None:
        lines.append(f"Correct: {recap.correct} of {recap.graded} ({recap.accuracy_pct}%)")
    if recap.concepts:
        lines.append("Concepts you got right: " + ", ".join(recap.concepts))
    if recap.current_streak > 0:
        lines.append(f"Current streak: {recap.current_streak} days")

    text = (
        f"Your week on CodeReader, {span}.\n\n"
        + "\n".join(lines)
        + f"\n\n{origin}/profile"
        + footer_text
    )
    html = (
        f"<p>Your week on CodeReader, {span}.</p><ul>"
        + "".join(f"<li>{line}</li>" for line in lines)
        + f'</ul><p><a href="{origin}/profile">See the full picture</a></p>'
        + footer_html
    )
    return OutboundEmail(
        to=to,
        subject=f"Your week on CodeReader, {span}",
        text=text,
        html=html,
        dev_link=link,
        headers=_unsubscribe_headers(user_id, "recap"),
    )
