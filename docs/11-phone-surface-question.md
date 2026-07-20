# 11 : Is the phone a first-class surface?

> **STATUS: RESOLVED, 2026-07-21. ANSWER A -- the phone IS a first-class
> surface.** Decided by building it: the viewer rebuild shipped and is merged to
> master. Nothing below is awaiting a decision. The rest of this document is
> kept as the EVIDENCE that motivated the rebuild (the measurements, the three
> defects, the options weighed), not as a live question.
>
> Where the answer was implemented:
> - **D-129** the code viewer moves to a model that survives new exercise types
>   (and **D-129 AMENDED** for the wrap tension)
> - **D-130** the mobile layout: desktop separates in SPACE, mobile in TIME
> - **D-131** phone-surface follow-ups: line-height, nav targets, sheet copy
> - **D-132** the mobile viewer was unusable at 400px: five measured defects
> - **D-133** the code pane could latch shut: root cause, not the guessed one
> - **D-134** the bottom sheet withdrawn; two full-screen narrow states replace it
> - **D-135** reaching the dev app from a phone on the LAN
> - **D-136** seeded specs intermittently flaky -- **STILL OPEN**, the only part
>   of this work that is not settled
>
> The three blocked items are all addressed: the code pane and the
> predict_the_fix options by the two-state narrow layout (D-130, D-134), and the
> line-number tap target by D-131/D-132.
>
> The "Recommendation" section below reasons from a 20-30 person beta invite.
> That framing is also withdrawn -- the launch is a full public launch (see
> HANDOFF) -- but the recommendation it reached, A, is the one that was taken.

Historical framing follows, unchanged.

Status when written: OPEN QUESTION, awaiting a product decision. Not a design
question, which is why it was not resolved inside docs/08.

This blocked three things already identified and specified: the code pane on
narrow viewports, the predict_the_fix answer options on narrow viewports, and
the spot_the_bug line-number tap target. All three were held pending the answer
here.

## Why this is being asked now

A narrow-viewport pass (375x667 and 360x480, real browser, real backend, with a
session built from the LONGEST live code payload of each type) found the app
structurally sound and the core content close to unusable.

Sound: no horizontal document overflow on any screen at either width, and no
clipped-and-unreachable content anywhere (the D-125 class). Dashboard, the A1
welcome-back and restore panel, Profile with all six panels, the A2 email
states, review and verify-email all fit or scroll correctly.

Close to unusable:

1. **The code pane shows about seven lines in a roughly 285px-wide window while
   lines need up to 962px.** You read roughly 30% of a line and scroll in two
   axes through a letterbox. Worst on spot_the_bug, where the instruction is
   "Tap the line number in the code where the bug is" and you cannot read the
   line you are being asked to judge.
2. **predict_the_fix answer options measure 576px inside a 375px viewport.**
   Each option is a full code block, so choosing between them, which is the
   entire interaction, requires sideways scrolling per option.
3. **The spot_the_bug line-number buttons are 47x24**, against a 44x44 guideline,
   and this one CANNOT be fixed independently (see below).

Screenshots for all of it were taken during the pass.

## The question

**Is the phone a first-class surface for this product, or is this desktop-first
with a mobile fallback?**

The tension is real in both directions, which is why it needs deciding rather
than assuming:

- FOR phone being first-class: the product is a 5-10 minute daily habit, which
  is a phone-shaped moment. It is already a PWA with a service worker and is
  meant to be installed. docs/00's whole retention argument is about returning
  daily, and daily habits live on phones.
- AGAINST: the thing being practised is READING CODE. Code is a
  horizontally-extended medium and professional developers read it on wide
  screens. The audience is working developers, who have a laptop. A cramped
  phone experience may be worse than an honest "open this on a laptop".

## Answer A: the phone is first-class

Then the code pane needs its own phone layout, and that is a real piece of work.

**Leading option: a full-viewport-height code pane, a smaller type step, and
soft-wrap with a visible continuation marker.**
- Full height, because the current fixed-height box wastes the one dimension a
  phone has. Seven lines becomes roughly twenty.
- A smaller type step, because character width is the binding constraint; one
  step down buys a meaningful number of columns.
- Soft-wrap with a continuation marker, so no line is ever cut off horizontally
  and the two-axis scroll becomes one-axis.

**THE TRADEOFF, and it is the load-bearing one: soft-wrap breaks the 1:1
mapping between gutter line numbers and visual rows, and the spot_the_bug
interaction is built on that mapping.** A wrapped line occupies two visual rows
but is still one logical line with one number. The gutter must then either
stretch its button across the wrapped rows (keeping 1:1 logical mapping, at the
cost of variable-height targets) or repeat/blank the number (visually clearer,
but the tap target becomes ambiguous). This is the part that needs designing,
not just configuring.

Alternatives considered, and why they are second-best: horizontal scroll only
with a bigger pane (keeps 1:1 mapping, keeps the letterbox); font scaling alone
(does not fix the longest lines, and pushes body text under AA); a separate
"phone mode" content set with shorter code (a content problem disguised as a
layout one, and it changes what is being practised).

**This also resolves the tap-target blocker.** The spot_the_bug line buttons are
47x24 because their height IS the code line-height (`text-code leading-relaxed`)
and must stay 1:1 with the code rows. They cannot be padded to 44px
independently without desynchronising the gutter from the code. Expanding the
hit area with negative margins is actively wrong here, because adjacent line
buttons would overlap and a mistap would select the WRONG line, which is the
answer. So the only correct fix is to raise the code line-height on narrow
viewports, which is the same lever as the density decision above.

Other implications if the answer is A:
- **PWA and install prompt:** the service worker already ships and nobody has
  audited what it caches or whether a stale shell survives a deploy. If phone is
  first-class, the install prompt becomes a real surface with its own copy and
  timing, and the caching story becomes a launch blocker rather than a curiosity.
- **Beta invite copy:** it should say the app works on a phone, and the invite
  should be openable on one. Right now nothing claims that and it would not be
  true.
- **Milestone:** yes, its own. It is a code-pane redesign plus a gutter
  interaction change plus a PWA pass. Folding it into A3 would sink A3.

## Answer B: desktop-first, mobile fallback

Then the current state is close to acceptable and the work is much smaller.

- The code pane keeps horizontal scroll; it is honest about being a desktop
  medium.
- Fix only the tap targets that are independent of code layout (nav, Sign out,
  I don't know, the dispute trigger, the email controls, the restore
  affordance). The spot_the_bug line buttons stay 47x24 and that is accepted and
  recorded, because on a phone the flagship interaction is degraded by design.
- **PWA:** stop treating install as a goal. Either drop the install prompt or
  scope the PWA to offline-resilience on desktop.
- **Beta invite copy:** say so. "Best on a laptop" in the invite is a small
  sentence that prevents a bad first session, and a bad first session in a
  20-30 person beta is expensive.
- **Milestone:** no. A half-day of tap-target work inside an existing phase.

## What is NOT in question

The structural fixes already landed and are not affected either way: D-125's
scroll containers, the onboarding screen (verified clean at 360x480), and the
absence of horizontal document overflow. Whatever the answer, those stay.

## Recommendation

If the beta invite is going out to 20-30 working developers who will open it
wherever they happen to be, **A**, with the code pane as its own milestone
before the invites. If the beta is explicitly framed as a desk activity, **B**
plus one honest sentence in the invite copy is the cheaper and more honest
answer. The worst outcome is the current one: shipping a PWA that invites
installation onto a device where the core interaction does not work well.
