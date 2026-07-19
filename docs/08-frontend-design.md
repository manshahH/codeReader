# 08 : Frontend Design Direction

This doc exists so the M6 build has a design north star instead of defaulting
to the statistical mean of scraped landing pages. It sets the brief, the
constraints, and a v1 token proposal. The final tokens are decided during the
M6 pre-flight (below), not here; but every constraint in this doc is binding.

## Required skills during M6
The M6 builder MUST load and apply, in this order:
1. `anti-slop-frontend` (detection and avoidance field guide)
2. `ui-ux-promax` (Mohsin's GitHub-sourced skill)
3. `frontend-design` if available in the environment
Skill folders live in `skills/` in this repo so Claude Code picks them
up. The M6 workflow is: pre-flight design plan -> self-critique against the
skills -> build from tokens -> audit against the slop catalogue before the
milestone is called done. A screen that triggers 4+ catalogue patterns fails
the milestone.

## The brief (one line)
A quiet, daily reading room for code: working developers spend 5-10 focused
minutes reading, tracing, and judging real-looking code, and leave feeling
sharper. The page's single job is to make reading code feel like reading a
beautifully typeset book, not like using a SaaS dashboard.

## Grounding: this subject's own materials
Everything distinctive should come from the world of reading code, not from
startup-landing vernacular: monospace type, line numbers, gutters, diff marks,
syntax color, the margins of well-printed programming books (K&R, SICP), paper
annotations, a reviewer's pen. NOT from: gradients, glassmorphism, icon-card
grids, mascots, confetti.

## The signature primitive: the gutter
One structural idea, repeated everywhere until it reads as identity:
every code block has a line-number gutter, so the ENTIRE INTERFACE adopts the
gutter as its layout spine. Concretely:
- Content columns sit to the right of a thin left gutter rail across the app.
- Progress through a session = marks in the gutter (like breakpoint dots).
- Streak history = a column of gutter tick marks, not a flame emoji.
- The answer reveal annotates the code the way a reviewer marks a printout:
  explanation notes connect to line numbers in the gutter margin.
- Selecting a line in spot_the_bug happens IN the gutter (tap the line
  number), which makes the core interaction literally live inside the
  signature element.
This is the one place boldness is spent. Everything else stays quiet.

## Typography (personality lives here)
- Code face: a characterful monospace with real italics and clear zero/O and
  1/l distinction. v1 proposal: Commit Mono or Iosevka (custom build), sized
  generously (15-16px on mobile) because reading IS the product. JetBrains
  Mono acceptable fallback, never the identity.
- Explanation face: the explanation is the product, so it gets a genuine book
  serif, not a UI grotesque. v1 proposal: Source Serif 4 or Charter, set at a
  comfortable measure (~65ch), real line-height (1.6+).
- UI face: one quiet sans for chrome (labels, buttons, nav), deliberately
  chosen, NOT Inter/Poppins/Space Grotesk/Geist by default. v1 proposal:
  IBM Plex Sans (pairs with the engineering register) or a system stack if
  restraint wins the pre-flight.
- Scale: one intentional type scale defined in tokens; no per-component sizes.

## Color: a semantic law, then a palette
The law comes first and is non-negotiable:
**Green and red are reserved exclusively for correctness (pass/fail, correct/
incorrect, diff added/removed). They never appear decoratively.** This turns
the diff heritage into a discipline: when the user sees green, it always means
the same thing. Most apps waste these colors; ours cannot.

Palette v1 proposal (pre-flight may refine hues, not the structure):
- Reading surface, light default: paper-white with a cool graphite cast
  (near #FAFAF7 / ink #1C1E21), explicitly NOT the warm-cream + terracotta
  cluster the slop calibration names.
- Dark mode: offered, user-chosen, never the default; must pass WCAG AA
  (4.5:1 body). Dark-by-default is the single most common slop tell.
- One accent for interaction: an "annotation ink" blue in the marginalia
  tradition (marking pen on paper), used for selection, links, primary action.
  Never purple/lavender-indigo, never a gradient.
- Syntax theme: ONE custom, muted theme derived from the palette (both
  modes), tuned for reading rather than editing: fewer hues, stronger
  structure. Not a stock Dracula/Monokai drop-in.
All values live in a single token file (CSS variables with semantic names:
--color-correct, --color-action, --surface-reading). Components never invent
values.

## Layout and structure
- Mobile-first; the archetypal session happens on a phone in a spare 10
  minutes. Code blocks keep the gutter pinned and are never shrunk below
  readability. How long lines are shown depends on available width (D-130):
  they SOFT-WRAP below the breakpoint, where horizontal scroll inside a 360px
  column costs the reader the left edge of every line, and they SCROLL above
  it, where there is width to spare and the authored line structure is worth
  preserving. Both are overridable by a persisted user preference exposed on
  the code block itself. This supersedes this doc's original "never wrapped",
  which was written before the narrow layout existed; see D-129/D-130.
- Below the breakpoint, code and interaction separate in TIME rather than in
  space: two FULL-SCREEN states with an explicit toggle (D-134). Reading
  state, where the code owns the entire viewport; answering state, where the
  answer UI does, with a persistent way back and the submit control pinned.
  The earlier bottom sheet is withdrawn: it claimed to separate in time but
  separated in space, and at 375x667 it clipped options and put submit out
  of reach. Above the breakpoint the two-column arrangement stands unchanged.
- EXCEPTION to "nothing else competing", granted narrowly (D-134): in the
  reading state, `trace` may pin ONE clamped line showing the option the
  reader has currently selected. trace asks you to compare candidate OUTPUTS
  against the code, and that comparison IS the exercise; without the line,
  verifying a candidate means holding a 40-character string in working
  memory across a state switch, which tests memory rather than reading. It
  renders ONLY once an option is selected -- never as an empty bar on first
  read, when there is nothing to verify and the code should be alone -- and
  it is one line, not a panel. No other type gets it.
- No cards-with-icon grids, no stat banners, no numbered 1-2-3 sections
  unless the content is truly a sequence, no colored left-borders on cards,
  no pill badges over headlines.
- Spacing and radius vary intentionally to build hierarchy; identical 16px
  radius on everything is the tell to avoid. Reading surfaces are calm and
  near-flat; elevation is reserved for the one thing that needs attention.
- The session player is a single focused column: context note, code (the
  hero of every screen), answer control, nothing else competing.

## Motion
Purposeful only: the answer reveal is THE orchestrated moment (the gutter
mark lands, the explanation annotations draw in beside their lines, the
streak tick appears last). Under 300ms per element, transform/opacity only,
custom easing, prefers-reduced-motion respected. No scroll-triggered fade-ins,
no hover glows, no bouncing indicators.

## Copy voice
Specific over clever, from the user's side of the screen. The app never
cheers ("Awesome job!!"), it respects: "Correct. 31% of readers caught this."
Buttons say what happens: "Check answer," "Show explanation," "Next." Errors
say what went wrong and what to do. Empty states invite the day's session.
The percentile line is the personality: dry, factual, quietly competitive.

## Screens (MVP surface, per docs/03)
login -> onboarding (level pick, one screen) -> today's session player ->
reveal (annotated code + explanation + percentile + streak) -> session
complete -> profile (streak column, accuracy, weakest concepts) -> dispute
modal. Each screen's hero is the content itself; chrome stays minimal.

## Quality floor (part of M6 done-when, additive to docs/06)
- Zero slop-catalogue score of 4+ on any screen (audited, documented).
- WCAG AA contrast both modes; visible keyboard focus; reduced motion.
- Lighthouse mobile perf >= 85 (already in M6).
- The one-glance test passes: a screenshot of the session player could not
  belong to any other product, because the gutter signature and the
  book-serif explanations are ours.
