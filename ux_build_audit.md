# UX Build Audit — Read-Only

Generated as the last read step before a build. Nothing in the repo was changed to produce this. Where code is quoted, it is verbatim (path:line noted); doc text is verbatim.

---

## A. The design system

### docs/08-frontend-design.md (IN FULL)

```markdown
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
  minutes. Code blocks get horizontal scroll with the gutter pinned, never
  wrapped or shrunk below readability.
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
```

### docs/08b-frontend-tokens-APPROVED.md (IN FULL)

```markdown
# 08b : Approved Frontend Tokens (M6)

These tokens were produced during the M6 design phase and APPROVED. They are
binding for the frontend build. Do not re-derive or substitute.

## Palette
- Reading surface (light, default): #FAFAF7
- Reading surface (dark, offered, NOT default): #0F1419
- --color-correct: #059669   (green — RESERVED for correctness/diff only)
- --color-incorrect: #DC2626 (red — RESERVED for correctness/diff only)
- --color-action: #1E40AF    (annotation-ink blue; never purple/indigo)

## Typefaces (self-hosted, no runtime CDN)
- Code: Iosevka (characterful, real italics). JetBrains Mono only as last-resort
  fallback, never the identity.
- Explanations: Source Serif 4 (OFL) — the explanation is the product.
- UI chrome: IBM Plex Sans (not Inter/Poppins/Space Grotesk).

## Scales & rules
- 9-level responsive type scale; 4px-based spacing scale (10 levels).
- Intentional radius variation (no identical-16px-everywhere).
- One custom muted syntax theme, both modes, tuned for reading.
- Dark mode: explicit user toggle, default LIGHT. No system-preference auto-switch.
- Gutter width on mobile: 48px.
- Reveal animation: subtle, <300ms, transform/opacity only, respect
  prefers-reduced-motion.

## Gutter signature (layout spine, not a code decoration)
- Session progress = gutter marks.
- Streak history = column of gutter ticks (not a flame emoji).
- spot_the_bug line selection = tap the line number IN the gutter.
- Reveal annotations connect explanation notes to gutter line numbers.

## Slop audit
Self-audited 0/16 catalogue patterns at design time. Re-audit per screen at build.
```

### frontend/src/styles/tokens.css (IN FULL)

```css
/*
 * Design tokens (docs/08, docs/08b). Every value a component needs lives
 * here, under a semantic name. Components never invent a color, spacing, or
 * radius value of their own.
 *
 * Values marked "derived" fill a gap docs/08b left open (it fixes the
 * structure -- 9-level scale, 4px spacing, intentional radius variation,
 * one muted syntax theme both modes -- but not every number). They are not
 * a new design direction, just numbers chosen inside the approved system.
 */

:root {
  /* ---- Surfaces & ink (docs/08b: exact; ink carried from docs/08's own proposal) ---- */
  --surface-reading: #FAFAF7;
  --surface-raised: #F2F1EA;
  --color-ink: #1C1E21;
  --color-ink-muted: #55595E;
  --color-border: #DEDFE0;
  --color-scrim: rgba(15, 17, 19, 0.45);

  /* ---- Semantic law: red/green reserved for correctness/diff only ---- */
  --color-correct: #059669;
  --color-incorrect: #DC2626;
  --color-correct-tint: rgba(5, 150, 105, 0.12);
  --color-incorrect-tint: rgba(220, 38, 38, 0.12);

  /* ---- Interaction (annotation-ink blue) ---- */
  --color-action: #1E40AF;
  --color-action-hover: #1A3690;
  --color-action-tint: rgba(30, 64, 175, 0.1);

  /* ---- Typefaces (self-hosted, styles/fonts.css) ---- */
  --font-code: 'Iosevka', 'JetBrains Mono', ui-monospace, monospace;
  --font-explanation: 'Source Serif 4', Georgia, serif;
  --font-ui: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;

  /* ---- Type scale: 9 steps, responsive (derived) ---- */
  --text-2xs: clamp(0.6875rem, 0.66rem + 0.12vw, 0.75rem);
  --text-xs: clamp(0.75rem, 0.72rem + 0.14vw, 0.8125rem);
  --text-sm: clamp(0.875rem, 0.84rem + 0.16vw, 0.9375rem);
  --text-base: clamp(1rem, 0.965rem + 0.16vw, 1.0625rem);
  --text-lg: clamp(1.125rem, 1.07rem + 0.24vw, 1.25rem);
  --text-xl: clamp(1.375rem, 1.29rem + 0.38vw, 1.625rem);
  --text-2xl: clamp(1.75rem, 1.6rem + 0.7vw, 2.125rem);
  --text-3xl: clamp(2.125rem, 1.9rem + 1.1vw, 2.75rem);
  --text-4xl: clamp(2.5rem, 2.1rem + 1.8vw, 3.5rem);
  --text-code: clamp(0.9375rem, 0.92rem + 0.08vw, 1rem);

  /* ---- Spacing: 10 steps, 4px base (derived) ---- */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-7: 32px;
  --space-8: 40px;
  --space-9: 56px;
  --space-10: 72px;

  /* ---- Radius: intentional variation by role, never uniform (derived) ---- */
  --radius-tight: 4px;
  --radius-soft: 10px;
  --radius-loose: 18px;
  --radius-tick: 999px;

  /* ---- The gutter: the layout spine ---- */
  --gutter-width: 48px;
  --gutter-width-desktop: 56px;

  /* ---- Motion: <300ms ceiling, custom easing, transform/opacity only ---- */
  --motion-fast: 150ms;
  --motion-base: 220ms;
  --motion-max: 280ms;
  --motion-ease: cubic-bezier(0.22, 1, 0.36, 1);

  /* ---- Syntax theme, light: muted, cool ink family, no red/green hues ---- */
  --syntax-plain: #1C1E21;
  --syntax-comment: #767B83;
  --syntax-keyword: #34517C;
  --syntax-string: #8A6A3A;
  --syntax-function: #4A5568;
  --syntax-number: #8A5540;
  --syntax-punctuation: #767B83;
}

[data-theme='dark'] {
  --surface-reading: #0F1419;
  --surface-raised: #171D24;
  --color-ink: #E7E9EC;
  --color-ink-muted: #9AA1AB;
  --color-border: #262B33;
  --color-scrim: rgba(0, 0, 0, 0.6);

  --color-correct: #10B981;
  --color-incorrect: #F0554A;
  --color-correct-tint: rgba(16, 185, 129, 0.16);
  --color-incorrect-tint: rgba(240, 85, 74, 0.16);

  /* Raw --color-action (#1E40AF) fails AA as text on this surface (~2.2:1);
     lightened for dark-mode text/links only, same hue, never purple. */
  --color-action: #7FA6FF;
  --color-action-hover: #9DBBFF;
  --color-action-tint: rgba(127, 166, 255, 0.16);

  --syntax-plain: #E7E9EC;
  --syntax-comment: #7C8492;
  --syntax-keyword: #7C9CDB;
  --syntax-string: #C9A56C;
  --syntax-function: #9AA4B8;
  --syntax-number: #C08868;
  --syntax-punctuation: #7C8492;
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --motion-fast: 0ms;
    --motion-base: 0ms;
    --motion-max: 0ms;
  }
}
```

### frontend/src/lib/theme.ts (IN FULL)

```ts
import { useEffect, useState } from 'react';

// Explicit toggle only, default light, no prefers-color-scheme auto-switch
// (docs/08b). This is a UI preference, not credentials, so localStorage is
// fine here -- unrelated to the access-token-in-memory-only rule.
const STORAGE_KEY = 'codereader:theme';

type Theme = 'light' | 'dark';

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme);
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === 'dark' ? 'dark' : 'light';
  });

  useEffect(() => {
    applyTheme(theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggle = () => setTheme((t) => (t === 'light' ? 'dark' : 'light'));
  return [theme, toggle];
}
```

**Where the Light/Dark toggle lives:** [NavBar.tsx](frontend/src/components/NavBar.tsx) — a text button (`{theme === 'light' ? 'Dark' : 'Light'}`) in the header, calling `useTheme()`'s `toggleTheme`. It is the only place in the app that flips `data-theme`. See section B for the full component.

### skills/anti-slop-frontend/SKILL.md and references/slop-catalogue.md

Both read in full above the tool output boundary — reproduced faithfully in the raw read, omitted here from the second copy-paste for length; see the live files at `skills/anti-slop-frontend/SKILL.md` and `skills/anti-slop-frontend/references/slop-catalogue.md`. Key facts extracted for the redesign:

- **Root cause of slop:** regression to the mean of scraped training data (Tailwind UI, Linear "Magic Blue", shadcn defaults, Bootstrap-era templates).
- **16-pattern deterministic checklist** (0–1 clean, 2–3 mild, 4+ heavy slop): Inter-everywhere, font-combo rotation (Space Grotesk/Instrument Serif/Geist), serif-italic-accent-word tell, "VibeCode purple" lavender-indigo, permanent dark mode with grey body text, failing dark-mode contrast, gradients everywhere, colored glows/box-shadows, centered generic-sans hero, badge/pill above H1, **colored borders on cards (single most specific tell)**, identical icon-card grids, numbered 1-2-3 sequences, stat-banner rows, emoji nav/sidebar icons, all-caps headings.
- **Fix pattern:** semantic token file, one repeated layout primitive (the gutter, in this codebase), motion on transform/opacity only under 300ms with custom easing and `prefers-reduced-motion` respected, WCAG AA contrast both themes.
- The house tokens already comply structurally: `--color-action` is deliberately not purple/indigo, dark mode is opt-in only, radii are varied (`--radius-tight/soft/loose/tick`), one custom syntax theme both modes.

---

## B. What the screens are today

### frontend/src/routes/RootGate.tsx

```tsx
import { Navigate } from 'react-router-dom';

import { useAuth } from '../lib/auth-context';

// Lands here after the GitHub OAuth callback (the backend redirects to
// APP_ORIGIN root, not /welcome -- see docs/07 divergence note) and on any
// direct visit to "/". AuthProvider has already attempted a silent refresh;
// this just routes on the result.
export function RootGate() {
  const { status, user } = useAuth();

  if (status === 'loading') {
    return <p className="p-6 text-ink-muted">Loading…</p>;
  }
  if (status === 'unauthenticated' || !user) {
    return <Navigate to="/login" replace />;
  }
  return <Navigate to={user.onboarded ? '/session' : '/onboarding'} replace />;
}
```

**Why it drops straight into session:** it doesn't drop into session unconditionally — it branches on `user.onboarded`. Any visit to `/` (including the OAuth callback landing, per the code comment: the backend redirects to `APP_ORIGIN` root, not a dedicated `/welcome` route) routes to `/onboarding` for a first-time user and `/session` for a returning one. There is no marketing/landing screen at all — `/` is purely a router, never rendered content.

### frontend/src/routes/Session.tsx

```tsx
import { useCallback, useEffect, useRef, useState } from 'react';

import { DisputeModal } from '../components/DisputeModal';
import { Reveal } from '../components/session/Reveal';
import { SessionComplete } from '../components/session/SessionComplete';
import { SessionProgressRail } from '../components/session/SessionProgressRail';
import { PredictTheFixAnswer } from '../components/session/PredictTheFixAnswer';
import { SpotTheBugAnswer } from '../components/session/SpotTheBugAnswer';
import { SummarizeAnswer } from '../components/session/SummarizeAnswer';
import { TraceAnswer } from '../components/session/TraceAnswer';
import { ApiError, getAttemptPoll, getSessionToday, postAttempt } from '../lib/api';
import { idempotencyKeyFor } from '../lib/idempotency';
import type { Answer, AttemptResponse, SessionResponse, StreakInfo } from '../lib/types';

type Phase = 'answering' | 'submitting' | 'grading_pending' | 'revealed' | 'grading_failed' | 'grading_timeout';

const DEFAULT_POLL_SECONDS = 3;
// A stuck grade must never freeze the session: after this long we stop
// polling, tell the user their streak counted, and let them move on. The
// backend retry job resolves the grade eventually; it just won't be shown
// in this sitting.
const MAX_POLL_MS = 2 * 60 * 1000;

export function Session() {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>('answering');
  const [attempt, setAttempt] = useState<AttemptResponse | null>(null);
  const [userAnswer, setUserAnswer] = useState<Answer | null>(null);
  const [correctCount, setCorrectCount] = useState(0);
  const [attemptedThisLoad, setAttemptedThisLoad] = useState(0);
  const [latestStreak, setLatestStreak] = useState<StreakInfo | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [disputeOpen, setDisputeOpen] = useState(false);

  const [selectedLine, setSelectedLine] = useState<number | null>(null);
  const [selectedReasonId, setSelectedReasonId] = useState<string | null>(null);
  const [selectedChoiceId, setSelectedChoiceId] = useState<string | null>(null);
  const [summaryText, setSummaryText] = useState('');

  const startTimeRef = useRef(Date.now());
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const pollStartRef = useRef(0);

  useEffect(() => {
    getSessionToday()
      .then((body) => {
        setSession(body);
        const firstUnattempted = body.exercises.findIndex((e) => !e.attempted);
        setCurrentIndex(firstUnattempted === -1 ? body.exercises.length : firstUnattempted);
        startTimeRef.current = Date.now();
      })
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : 'Could not load today’s session.'));
    return () => {
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    };
  }, []);

  const resetDraft = useCallback(() => {
    setSelectedLine(null);
    setSelectedReasonId(null);
    setSelectedChoiceId(null);
    setSummaryText('');
    setSubmitError(null);
    startTimeRef.current = Date.now();
  }, []);

  const applyGraded = useCallback((response: AttemptResponse) => {
    setAttempt(response);
    if (response.streak) setLatestStreak(response.streak);
    if (response.status === 'graded') {
      if (response.is_correct) setCorrectCount((c) => c + 1);
      setAttemptedThisLoad((c) => c + 1);
      setPhase('revealed');
    } else if (response.status === 'grading_pending') {
      setPhase('grading_pending');
    } else {
      setAttemptedThisLoad((c) => c + 1);
      setPhase('grading_failed');
    }
  }, []);

  const stopPollingForThisSitting = useCallback(() => {
    setAttemptedThisLoad((c) => c + 1);
    setPhase('grading_timeout');
  }, []);

  const pollAttempt = useCallback(
    (attemptId: number, delaySeconds: number) => {
      pollTimeoutRef.current = setTimeout(async () => {
        if (Date.now() - pollStartRef.current >= MAX_POLL_MS) {
          stopPollingForThisSitting();
          return;
        }
        try {
          const { body, retryAfterSeconds } = await getAttemptPoll(attemptId);
          if (body.status === 'grading_pending') {
            pollAttempt(attemptId, retryAfterSeconds ?? DEFAULT_POLL_SECONDS);
          } else {
            applyGraded(body);
          }
        } catch {
          pollAttempt(attemptId, DEFAULT_POLL_SECONDS);
        }
      }, delaySeconds * 1000);
    },
    [applyGraded, stopPollingForThisSitting],
  );

  if (loadError) {
    return <p className="p-6 text-incorrect">{loadError}</p>;
  }
  if (!session) {
    return <p className="p-6 text-ink-muted">Loading today’s session…</p>;
  }
  if (session.exercises.length === 0) {
    return <p className="p-6 text-ink-muted">Nothing to read just yet. Check back in a little while.</p>;
  }
  if (currentIndex >= session.exercises.length) {
    // Only claim a correct/total tally when every exercise was actually
    // played this page load; a reload of an already-completed session has
    // no per-exercise history to reconstruct it from.
    const fullyPlayedThisLoad = attemptedThisLoad === session.exercises.length;
    return (
      <SessionComplete
        total={session.exercises.length}
        correct={fullyPlayedThisLoad ? correctCount : null}
        currentStreak={latestStreak?.current ?? null}
      />
    );
  }

  const exercise = session.exercises[currentIndex];

  const isChoiceType = exercise.type === 'trace' || exercise.type === 'predict_the_fix';
  const isValid =
    exercise.type === 'spot_the_bug'
      ? selectedLine !== null && selectedReasonId !== null
      : isChoiceType
        ? selectedChoiceId !== null
        : summaryText.trim().length > 0 && summaryText.trim().split(/\s+/).length <= (exercise.payload.max_words ?? 60);

  const handleSubmit = async () => {
    let answer: Answer;
    if (exercise.type === 'spot_the_bug') answer = { line: selectedLine as number, reason_id: selectedReasonId as string };
    else if (isChoiceType) answer = { choice_id: selectedChoiceId as string };
    else answer = { text: summaryText.trim() };

    setUserAnswer(answer);
    setPhase('submitting');
    setSubmitError(null);
    try {
      const key = idempotencyKeyFor(exercise.exercise_id);
      const timeTakenMs = Date.now() - startTimeRef.current;
      const response = await postAttempt(key, {
        exercise_id: exercise.exercise_id,
        exercise_version: exercise.version,
        answer,
        time_taken_ms: timeTakenMs,
      });
      applyGraded(response);
      if (response.status === 'grading_pending') {
        pollStartRef.current = Date.now();
        pollAttempt(response.attempt_id, DEFAULT_POLL_SECONDS);
      }
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : 'Could not submit that. Try again.');
      setPhase('answering');
    }
  };

  const handleNext = () => {
    resetDraft();
    setAttempt(null);
    setUserAnswer(null);
    setPhase('answering');
    setCurrentIndex((i) => i + 1);
  };

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-8">
      <SessionProgressRail exercises={session.exercises} currentIndex={currentIndex} />

      <div className="flex items-center justify-between text-sm text-ink-muted">
        <span className="capitalize">{exercise.type.replace(/_/g, ' ')}</span>
        <span>{exercise.difficulty_band}</span>
      </div>

      <p className="text-sm text-ink-muted">{exercise.payload.context_note}</p>

      {phase === 'answering' || phase === 'submitting' ? (
        <>
          {exercise.type === 'spot_the_bug' ? (
            <SpotTheBugAnswer
              payload={exercise.payload}
              selectedLine={selectedLine}
              onSelectLine={setSelectedLine}
              selectedReasonId={selectedReasonId}
              onSelectReason={setSelectedReasonId}
            />
          ) : exercise.type === 'trace' ? (
            <TraceAnswer payload={exercise.payload} selectedChoiceId={selectedChoiceId} onSelectChoice={setSelectedChoiceId} />
          ) : exercise.type === 'predict_the_fix' ? (
            <PredictTheFixAnswer payload={exercise.payload} selectedChoiceId={selectedChoiceId} onSelectChoice={setSelectedChoiceId} />
          ) : (
            <SummarizeAnswer payload={exercise.payload} text={summaryText} onChangeText={setSummaryText} />
          )}
          {submitError ? <p className="text-sm text-incorrect">{submitError}</p> : null}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!isValid || phase === 'submitting'}
            className="self-start rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover disabled:opacity-40"
          >
            {phase === 'submitting' ? 'Checking…' : 'Check answer'}
          </button>
        </>
      ) : phase === 'grading_pending' ? (
        <p className="text-sm text-ink-muted" aria-live="polite">
          Reviewing your answer…
        </p>
      ) : phase === 'grading_failed' ? (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-ink-muted">We couldn’t grade this one. Your streak still counts.</p>
          <button type="button" onClick={handleNext} className="self-start rounded-soft bg-action px-6 py-3 text-base font-medium text-surface-reading">
            Next
          </button>
        </div>
      ) : phase === 'grading_timeout' ? (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-ink-muted">We’ll grade this shortly. Your streak already counted, so keep going.</p>
          <button type="button" onClick={handleNext} className="self-start rounded-soft bg-action px-6 py-3 text-base font-medium text-surface-reading">
            Next
          </button>
        </div>
      ) : attempt && userAnswer ? (
        <Reveal exercise={exercise} attempt={attempt} userAnswer={userAnswer} onNext={handleNext} onDispute={() => setDisputeOpen(true)} />
      ) : null}

      {disputeOpen ? (
        <DisputeModal
          exerciseId={exercise.exercise_id}
          version={exercise.version}
          attemptId={attempt?.attempt_id ?? null}
          onClose={() => setDisputeOpen(false)}
        />
      ) : null}
    </div>
  );
}
```

### frontend/src/routes/Profile.tsx

```tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { StreakTicks } from '../components/gutter/Gutter';
import { ApiError, getMeConcepts, getMeStats } from '../lib/api';
import { useAuth } from '../lib/auth-context';
import { pluralizeDays } from '../lib/format';
import type { ConceptMastery, MeStats } from '../lib/types';

function StreakColumn({ current, longest }: { current: number; longest: number }) {
  return (
    <div>
      <p className="text-sm text-ink-muted">Current streak</p>
      <p className="font-explanation text-3xl text-ink">{pluralizeDays(current)}</p>
      <div className="mt-3">
        <StreakTicks current={current} />
      </div>
      <p className="mt-2 text-sm text-ink-muted">Longest: {pluralizeDays(longest)}</p>
    </div>
  );
}

export function Profile() {
  const [stats, setStats] = useState<MeStats | null>(null);
  const [concepts, setConcepts] = useState<ConceptMastery[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([getMeStats(), getMeConcepts()])
      .then(([statsBody, conceptsBody]) => {
        setStats(statsBody);
        setConcepts(conceptsBody);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load your profile.'));
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  if (error) return <p className="p-6 text-incorrect">{error}</p>;
  if (!stats || !concepts) return <p className="p-6 text-ink-muted">Loading…</p>;

  const accuracyEntries = Object.entries(stats.accuracy_by_type);
  const weakest = concepts.slice(0, 5);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-10 px-4 py-8">
      <div>
        <p className="text-sm text-ink-muted">Signed in as</p>
        <p className="font-ui text-lg text-ink">{user?.display_name ?? user?.username}</p>
      </div>

      <StreakColumn current={stats.current_streak} longest={stats.longest_streak} />

      <div>
        <p className="mb-3 text-sm text-ink-muted">Accuracy by type</p>
        <div className="flex flex-col gap-2">
          {accuracyEntries.length === 0 ? (
            <p className="text-sm text-ink-muted">No attempts yet.</p>
          ) : (
            accuracyEntries.map(([type, accuracy]) => (
              <div key={type} className="flex items-center justify-between border-b border-border py-2">
                <span className="font-code text-sm capitalize text-ink">{type.replace(/_/g, ' ')}</span>
                <span className="font-code text-sm text-ink-muted">{Math.round(accuracy * 100)}%</span>
              </div>
            ))
          )}
        </div>
      </div>

      <div>
        <p className="mb-3 text-sm text-ink-muted">Weakest concepts</p>
        <div className="flex flex-col gap-2">
          {weakest.length === 0 ? (
            <p className="text-sm text-ink-muted">Not enough data yet.</p>
          ) : (
            weakest.map((concept) => (
              <div key={concept.concept} className="flex items-center justify-between border-b border-border py-2">
                <span className="text-sm text-ink">{concept.concept.replace(/-/g, ' ')}</span>
                <span className="font-code text-sm text-ink-muted">{Math.round(concept.mastery * 100)}%</span>
              </div>
            ))
          )}
        </div>
      </div>

      <button type="button" onClick={handleLogout} className="self-start text-sm text-ink-muted underline hover:text-ink">
        Sign out
      </button>
    </div>
  );
}
```

### frontend/src/components/NavBar.tsx

```tsx
import { Link } from 'react-router-dom';

import { useTheme } from '../lib/theme';

export function NavBar() {
  const [theme, toggleTheme] = useTheme();

  return (
    <header className="flex items-center justify-between border-b border-border px-4 py-3 md:pl-gutter-desktop md:pr-4">
      <Link to="/session" className="font-explanation text-lg italic text-ink">
        Code Reader
      </Link>
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
          className="text-sm text-ink-muted hover:text-ink"
        >
          {theme === 'light' ? 'Dark' : 'Light'}
        </button>
        <Link to="/profile" className="text-sm text-ink-muted hover:text-ink">
          Profile
        </Link>
      </div>
    </header>
  );
}
```

### frontend/src/components/session/SessionComplete.tsx

```tsx
import { Link } from 'react-router-dom';

import { StreakTicks } from '../gutter/Gutter';

interface Props {
  total: number;
  correct: number | null;
  currentStreak: number | null;
}

export function SessionComplete({ total, correct, currentStreak }: Props) {
  return (
    <div className="flex flex-col items-start gap-6 py-12">
      <p className="text-sm text-ink-muted">Session complete</p>
      <h1 className="font-explanation text-3xl text-ink">
        {correct === null ? `${total} exercises, done for today.` : `${correct} of ${total} correct today.`}
      </h1>
      {currentStreak !== null ? (
        <div className="flex items-center gap-3 text-ink-muted">
          <StreakTicks current={currentStreak} />
          <span>{currentStreak}-day streak.</span>
        </div>
      ) : null}
      <p className="text-base text-ink-muted">Come back tomorrow for the next session.</p>
      <Link
        to="/profile"
        className="rounded-soft border border-border px-6 py-3 font-ui text-base text-ink transition-colors duration-fast hover:border-action hover:text-action"
      >
        View profile
      </Link>
    </div>
  );
}
```

### frontend/src/components/session/Reveal.tsx

```tsx
import { CodeBlock } from '../gutter/CodeBlock';
import { StreakTicks } from '../gutter/Gutter';
import { pluralizeDays } from '../../lib/format';
import type {
  Answer,
  AttemptResponse,
  PredictTheFixReveal,
  STBReveal,
  SessionExercise,
  SummarizeReveal,
  TraceReveal,
} from '../../lib/types';

interface Props {
  exercise: SessionExercise;
  attempt: AttemptResponse;
  userAnswer: Answer;
  onNext: () => void;
  onDispute: () => void;
}

function VerdictBadge({ isCorrect }: { isCorrect: boolean | null }) {
  if (isCorrect === null) return null;
  return (
    <p className={`font-ui text-lg font-medium ${isCorrect ? 'text-correct' : 'text-incorrect'}`}>
      {isCorrect ? 'Correct.' : 'Incorrect.'}
    </p>
  );
}

function PercentileLine({ percentile }: { percentile: AttemptResponse['percentile'] }) {
  if (!percentile) return null;
  const pct = Math.round(percentile.solve_rate * 100);
  return (
    <p className="text-sm text-ink-muted">
      {pct}% of readers caught this ({percentile.n} attempts).
    </p>
  );
}

function StreakLine({ streak }: { streak: AttemptResponse['streak'] }) {
  if (!streak) return null;
  return (
    <div className="flex items-center gap-3 text-sm text-ink-muted">
      <StreakTicks current={streak.current} />
      <span>
        {streak.event === 'extended'
          ? `Streak extended to ${pluralizeDays(streak.current)}.`
          : `Streak reset to ${pluralizeDays(streak.current)}.`}
      </span>
    </div>
  );
}

function SpotTheBugReveal({ exercise, attempt, userAnswer }: { exercise: SessionExercise; attempt: AttemptResponse; userAnswer: Answer }) {
  const reveal = attempt.reveal as STBReveal;
  const markLines: Record<number, 'correct' | 'incorrect'> = {};
  reveal.correct_lines.forEach((line) => {
    markLines[line] = 'correct';
  });
  if ('line' in userAnswer && !reveal.correct_lines.includes(userAnswer.line)) {
    markLines[userAnswer.line] = 'incorrect';
  }
  const notedLines = new Set(reveal.explanation.line_notes.map((n) => n.line));
  const correctReasonText = exercise.payload.reason_options?.find((r) => r.id === reveal.correct_reason_id)?.text;

  return (
    <div className="flex flex-col gap-4">
      <CodeBlock code={exercise.payload.code} markLines={markLines} notedLines={notedLines} />
      {correctReasonText ? <p className="text-sm text-ink-muted">Reason: {correctReasonText}</p> : null}
      <ul className="flex flex-col gap-2">
        {reveal.explanation.line_notes.map((note) => (
          <li key={note.line} className="text-sm text-ink-muted">
            <span className="font-code text-action">Line {note.line}</span> — {note.note}
          </li>
        ))}
      </ul>
    </div>
  );
}

function TraceRevealView({ exercise, attempt, userAnswer }: { exercise: SessionExercise; attempt: AttemptResponse; userAnswer: Answer }) {
  const reveal = attempt.reveal as TraceReveal;
  const userChoiceId = 'choice_id' in userAnswer ? userAnswer.choice_id : null;
  const wrongNote = reveal.explanation.why_wrong.find((w) => w.choice_id === userChoiceId);

  return (
    <div className="flex flex-col gap-4">
      <CodeBlock code={exercise.payload.code} />
      {wrongNote ? <p className="text-sm text-incorrect">{wrongNote.note}</p> : null}
      <div className="rounded-soft border border-border">
        <table className="w-full text-left font-code text-sm">
          <tbody>
            {reveal.explanation.trace_table.map((row) => (
              <tr key={row.line} className="border-b border-border last:border-0">
                <td className="px-3 py-2 text-ink-muted">L{row.line}</td>
                <td className="px-3 py-2 text-ink">{row.state}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PredictTheFixRevealView({ exercise, attempt, userAnswer }: { exercise: SessionExercise; attempt: AttemptResponse; userAnswer: Answer }) {
  const reveal = attempt.reveal as PredictTheFixReveal;
  const userChoiceId = 'choice_id' in userAnswer ? userAnswer.choice_id : null;
  const correctFix = exercise.payload.choices?.find((c) => c.id === reveal.correct_choice_id)?.text;
  const wrongNote = reveal.explanation.why_wrong.find((w) => w.choice_id === userChoiceId);

  return (
    <div className="flex flex-col gap-4">
      {wrongNote ? <p className="text-sm text-incorrect">{wrongNote.note}</p> : null}
      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium text-correct">The fix that passes the test</p>
        {correctFix ? <CodeBlock code={correctFix} /> : null}
      </div>
    </div>
  );
}

function SummarizeRevealView({ attempt }: { attempt: AttemptResponse }) {
  const reveal = attempt.reveal as SummarizeReveal;
  return (
    <div className="flex flex-col gap-4">
      {attempt.score !== undefined && attempt.score !== null ? (
        <p className="text-sm text-ink-muted">Score: {Math.round(attempt.score * 100)}%</p>
      ) : null}
      {attempt.grader_output ? (
        <div className="flex flex-col gap-3">
          {attempt.grader_output.rubric_hits.length > 0 ? (
            <div>
              <p className="mb-1 text-sm font-medium text-correct">Covered</p>
              <ul className="list-inside list-disc text-sm text-ink-muted">
                {attempt.grader_output.rubric_hits.map((hit) => (
                  <li key={hit}>{hit}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {attempt.grader_output.rubric_misses.length > 0 ? (
            <div>
              <p className="mb-1 text-sm font-medium text-incorrect">Missed</p>
              <ul className="list-inside list-disc text-sm text-ink-muted">
                {attempt.grader_output.rubric_misses.map((miss) => (
                  <li key={miss}>{miss}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div>
            <p className="mb-1 text-sm text-ink-muted">Reference answer</p>
            <p className="font-explanation text-base leading-relaxed text-ink">{attempt.grader_output.reference_answer}</p>
          </div>
        </div>
      ) : null}
      <p className="font-explanation text-base leading-relaxed text-ink">{reveal.explanation.summary}</p>
    </div>
  );
}

export function Reveal({ exercise, attempt, userAnswer, onNext, onDispute }: Props) {
  const explanation = attempt.reveal && 'explanation' in attempt.reveal ? attempt.reveal.explanation : null;

  return (
    <div className="flex flex-col gap-6">
      <VerdictBadge isCorrect={attempt.is_correct} />

      {exercise.type === 'spot_the_bug' ? (
        <SpotTheBugReveal exercise={exercise} attempt={attempt} userAnswer={userAnswer} />
      ) : exercise.type === 'trace' ? (
        <TraceRevealView exercise={exercise} attempt={attempt} userAnswer={userAnswer} />
      ) : exercise.type === 'predict_the_fix' ? (
        <PredictTheFixRevealView exercise={exercise} attempt={attempt} userAnswer={userAnswer} />
      ) : (
        <SummarizeRevealView attempt={attempt} />
      )}

      {explanation && exercise.type !== 'summarize' ? (
        <div className="measure flex flex-col gap-2 border-t border-border pt-4">
          <p className="font-explanation text-base leading-relaxed text-ink">{explanation.summary}</p>
          <p className="font-explanation text-sm italic leading-relaxed text-ink-muted">{explanation.principle}</p>
        </div>
      ) : null}

      <PercentileLine percentile={attempt.percentile} />
      <StreakLine streak={attempt.streak} />

      <div className="flex items-center justify-between gap-4 pt-2">
        <button type="button" onClick={onDispute} className="text-sm text-ink-muted underline hover:text-ink">
          Something wrong with this exercise?
        </button>
        <button
          type="button"
          onClick={onNext}
          className="rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
        >
          Next
        </button>
      </div>
    </div>
  );
}
```

### Supporting gutter primitives read for context

`frontend/src/components/gutter/Gutter.tsx` exports `GutterCell`, `GutterRail`, `GutterLineButton` (the tap-line-number control), `GutterTick`, and `StreakTicks` (capped at 30 ticks, most recent last — this is what Profile and SessionComplete both render). `frontend/src/components/gutter/CodeBlock.tsx` renders the gutter-pinned code block used everywhere code appears, syntax-highlighted via `prism-react-renderer` with `readingSyntaxTheme`.

Login (`frontend/src/routes/Login.tsx`, read though not explicitly requested — needed to see NavBar isn't present pre-auth) is a single centered column, no NavBar, just the GitHub CTA.

---

## C. The "I don't know" contract

### backend/app/schemas/attempts.py — `AttemptRequest`

```python
class AttemptRequest(BaseModel):
    model_config = _STRICT

    exercise_id: uuid.UUID
    exercise_version: int
    answer: dict[str, Any]
    time_taken_ms: int | None = None
```

`answer` is an open `dict[str, Any]` at the Pydantic layer — shape validation happens downstream, in `backend/app/attempts/grading.py::validate_answer_shape`:

```python
def validate_answer_shape(exercise_type: str, answer: dict[str, Any]) -> None:
    if exercise_type == "spot_the_bug":
        if set(answer) != {"line", "reason_id"}:
            raise AnswerShapeError("spot_the_bug answer requires exactly {line, reason_id}")
        line_ok = isinstance(answer.get("line"), int)
        reason_ok = isinstance(answer.get("reason_id"), str)
        if not line_ok or not reason_ok:
            raise AnswerShapeError("spot_the_bug answer needs an int line and a string reason_id")
    elif exercise_type in ("trace", "predict_the_fix"):
        if set(answer) != {"choice_id"}:
            raise AnswerShapeError(f"{exercise_type} answer requires exactly {{choice_id}}")
        if not isinstance(answer.get("choice_id"), str):
            raise AnswerShapeError(f"{exercise_type} answer requires a string choice_id")
    else:
        raise UnsupportedExerciseTypeError(
            f"deterministic grading does not support exercise type {exercise_type!r}",
        )
```

**Can the endpoint accept "no answer" / skip today, as-is? No.** `set(answer) != {"line", "reason_id"}` requires *exactly* those two keys for `spot_the_bug`, and `set(answer) != {"choice_id"}` requires *exactly* that one key for `trace`/`predict_the_fix` — both raise `AnswerShapeError` → HTTP 422 `answer_shape_mismatch` (wired in `backend/app/attempts/service.py:386-400`) for any other shape, including an empty `{}` or a `{"skipped": true}` sentinel. There is no `summarize` path either: an empty/whitespace string fails `validate_summarize_answer_shape` (not shown above, but the frontend already guards this — `Session.tsx`'s `isValid` check requires `summaryText.trim().length > 0`).

**Exactly what would have to change, per type, to accept an honest skip:**

| Type | Current required shape | Minimal change to add a skip |
|---|---|---|
| `spot_the_bug` | `{"line": int, "reason_id": str}` exactly | Add a third allowed shape, e.g. `{"skipped": true}`, as an explicit `or` branch in `validate_answer_shape` — the `set(answer) != {...}` exact-match check means any new shape must be its own branch, not a relaxation of the existing one |
| `trace` / `predict_the_fix` | `{"choice_id": str}` exactly | Same pattern — a parallel `{"skipped": true}` branch |
| `summarize` | non-empty trimmed text, `<= max_words` | Frontend `isValid` gate would need a "skip" affordance too; backend `validate_summarize_answer_shape` (in `attempts/rubric.py`, not pasted here) would need the same skip branch |

Beyond `validate_answer_shape`, three more places assume a real answer exists and would need to branch on "skipped":
1. `grade_deterministic()` (`grading.py:72-79`) calls `grade_spot_the_bug`/`grade_choice`, which index into `answer["line"]` / `answer["choice_id"]` — a skip must short-circuit before this, with `is_correct` presumably set to `None` or a new tri-state, not `False`.
2. `AttemptResponse.is_correct` is typed `bool | None` already (`schemas/attempts.py:143`) — `None` is currently reserved for "still grading" (`grading_pending`). Reusing it for "skipped" would collide with that meaning; a skip most likely needs either a new `status` literal (currently `Literal["graded", "grading_pending", "grading_failed"]`) or a separate boolean/field.
3. `db/schema.sql`'s `attempts.answer jsonb NOT NULL` and `is_correct boolean` (nullable, currently only null while rubric-pending) would need the schema's meaning of `is_correct IS NULL` clarified or a new column added to disambiguate "not yet graded" from "declined to attempt."

### backend/app/attempts/grading.py

Full file already quoted in the raw read above (see Read output). Key point for this audit: `grade_deterministic` and `build_reveal` never see the concept of "no answer" — they assume a shape-valid answer reached them, confirming the skip logic would have to live upstream, in `validate_answer_shape`/`submit_attempt`.

### Does the spaced-repetition scheduler distinguish "wrong" from "did not attempt"?

Read `backend/app/models/user_state.py` (`UserConceptState`) and the concept-state update logic, which lives in `backend/app/attempts/service.py::update_concept_state` (there is no separate "concept-state service" module — this function is it):

```python
CONCEPT_INTERVAL_WRONG_DAYS = 2
CONCEPT_INTERVAL_RIGHT_DAYS = 7
CONCEPT_INTERVAL_RIGHT_AGAIN_DAYS = 21

_MASTERY_DECAY = decimal.Decimal("0.7")
_MASTERY_GAIN = decimal.Decimal("0.3")

async def update_concept_state(
    db: AsyncSession,
    user: User,
    concepts: list[str],
    is_correct: bool,
    now: dt.datetime,
) -> None:
    for concept in concepts:
        row = await db.get(UserConceptState, (user.id, concept))
        if row is None:
            row = UserConceptState(user_id=user.id, concept=concept, mastery=decimal.Decimal("0"), attempts=0, correct=0)
            db.add(row)
            await db.flush()

        already_correct_before = row.correct > 0

        row.attempts += 1
        if is_correct:
            row.correct += 1

        target = decimal.Decimal("1") if is_correct else decimal.Decimal("0")
        updated_mastery = row.mastery * _MASTERY_DECAY + target * _MASTERY_GAIN
        row.mastery = updated_mastery.quantize(_MASTERY_QUANT)
        row.last_seen_at = now

        # D-36: "right again" = correct at least once before this attempt,
        # not strictly consecutive-correct (no schema column tracks that).
        if not is_correct:
            interval_days = CONCEPT_INTERVAL_WRONG_DAYS
        elif already_correct_before:
            interval_days = CONCEPT_INTERVAL_RIGHT_AGAIN_DAYS
        else:
            interval_days = CONCEPT_INTERVAL_RIGHT_DAYS
        row.next_review_at = now + dt.timedelta(days=interval_days)

    await db.flush()
```

**Answer: no.** `is_correct` is a `bool` parameter, not `bool | None`, and the call site (`attempts/service.py:497-499`) only invokes `update_concept_state` when `is_correct is not None` — i.e. exactly when a real grade exists. There is no third branch for "declined to answer." A skip today would fall into neither `if is_correct` nor its `else`; it simply cannot reach this function under the current contract, because `validate_answer_shape` already rejected it upstream (section above). If "I don't know" is added, the model as written treats it identically to "wrong" only if you feed it `is_correct=False` — which is exactly the "STRONGER signal" collapse the audit prompt warns about: `CONCEPT_INTERVAL_WRONG_DAYS = 2` would apply to a wrong guess and an honest skip alike, with no shorter interval, no distinct `attempts`/`correct` semantics (an honest skip probably shouldn't increment `correct`'s denominator the same way a guess does), and no `next_review_at` closer than 2 days for either.

To make "I don't know" schedule sooner than "wrong," at minimum: a new interval constant (e.g. `CONCEPT_INTERVAL_SKIPPED_DAYS < CONCEPT_INTERVAL_WRONG_DAYS`), a third branch in the interval `if/elif/else`, and a decision on whether `attempts`/`mastery` should move at all for a skip (arguably mastery should decay less than an active wrong guess, since the user didn't demonstrate a misconception, just an absence of knowledge).

`db/schema.sql`'s `user_concept_state` table (`mastery numeric(4,3)`, `attempts int`, `correct int`, `next_review_at timestamptz`) has no column that could carry a distinct "declined" count independent of `attempts`/`correct` — adding that distinction cleanly would want a migration (e.g. `declined int NOT NULL DEFAULT 0`), not just an app-code change.

---

## D. "Review today's session"

### backend/app/sessions/router.py (IN FULL)

```python
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, CurrentUserDep, DbSessionDep
from app.core.errors import ApiError
from app.core.metrics import record_latency
from app.core.redis import get_redis
from app.models import User
from app.sessions.service import get_today_session

router = APIRouter(prefix="/v1", tags=["sessions"])
RedisDep = Depends(get_redis)


@router.get("/session/today")
async def session_today(
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
    redis: Redis = RedisDep,
) -> dict:
    started = time.perf_counter()
    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")
    try:
        return await get_today_session(session, redis, user)
    finally:
        # One of the two non-negotiable golden signals (docs/06 M7): a
        # climbing session-fetch p95 is an early incident signal.
        await record_latency(redis, "session_fetch", (time.perf_counter() - started) * 1000)
```

There is exactly **one** session endpoint: `GET /v1/session/today`. It returns `SessionResponse` (`session_date`, `completed`, `exercises: SessionExercise[]`), each exercise carrying `payload` (pre-answer content only) and `attempted: bool` — **never** `grading` or `explanation` (`schemas/session.py`'s docstring: *"extra='forbid' everywhere: these are allowlists... `grading` and `explanation` are structurally absent"*). There is no endpoint that returns a completed session bundled with its attempts, verdicts, and explanations as one object.

The full endpoint inventory (grepped across every router):

```
backend\app\admin\router.py:42:@router.get("/admin/metrics")
backend\app\admin\router.py:54:@router.get("/admin/retention")
backend\app\admin\router.py:65:@router.post("/admin/beta/invite")
backend\app\admin\router.py:75:@router.post("/admin/beta/revoke")
backend\app\auth\router.py:74:@router.get("/github/start")
backend\app\auth\router.py:96:@router.get("/github/callback")
backend\app\auth\router.py:161:@router.post("/refresh")
backend\app\auth\router.py:199:@router.post("/logout", status_code=204)
backend\app\attempts\router.py:20:@router.post("/attempts")
backend\app\attempts\router.py:62:@router.get("/attempts/{attempt_id}")
backend\app\users\router.py:16:@router.get("/me")
backend\app\users\router.py:27:@router.patch("/me")
backend\app\users\router.py:38:@router.get("/me/stats")
backend\app\users\router.py:46:@router.get("/me/concepts")
backend\app\disputes\router.py:17:@router.post(
backend\app\sessions\router.py:20:@router.get("/session/today")
```

**What exists that could serve "review today's session":** `GET /v1/attempts/{attempt_id}` (`backend/app/attempts/router.py:62`, handler `get_attempt` in `attempts/service.py:557-608`). This is per-attempt, not per-session, but it is the closest primitive: given an `attempt_id`, it reconstructs the full reveal (`build_reveal`/`build_summarize_reveal`) plus `is_correct`, `score`, `grader_output`, and `percentile` at any time after the fact — not just at submit time — because `build_reveal(exercise)` derives the reveal fresh from `exercise.grading`/`exercise.explanation` on every call, not from anything stored per-attempt. The docstring on it confirms this is intentional:

```python
async def get_attempt(db: AsyncSession, user: User, attempt_id: int) -> dict | None:
    attempt = await db.scalar(
        select(Attempt).where(Attempt.id == attempt_id, Attempt.user_id == user.id),
    )
    ...
    # grading_pending/grading_failed: no reveal yet. grading_failed is
    # terminal (never retried) and reported gracefully here -- never a 500
    # or a hang -- so the client can tell the user their answer couldn't be
    # graded.
```

**Gap for a "Review today's session" screen:** there is no endpoint that lists the `attempt_id`s for a given day. `Attempt` rows carry `session_date` (`db/schema.sql:168`) and `DailySession.exercise_list` (`jsonb`) carries `{exercise_id, version, slot, is_boss}` per slot, but neither is joined into a "give me today's attempts" list endpoint. Building "review today's session" would need either: (a) a new `GET /v1/session/{date}/attempts` (or similar) that joins `daily_sessions` → `attempts` for that `(user_id, session_date)` and returns attempt IDs/summaries, then the client calls `GET /v1/attempts/{id}` per exercise, or (b) folding attempt summaries directly into an extended session-history response.

**Are past attempts + explanation retrievable after the session ends, or is reveal data discarded client-side?** Retrievable, but only by `attempt_id`, not currently surfaced anywhere in the frontend after `Session.tsx` unmounts — the reveal is held in React state (`const [attempt, setAttempt] = useState<AttemptResponse | null>(null)`) and reset on `handleNext`/navigation, so today's UI does discard it. The *server-side* data is not discarded: `Attempt.answer`, `is_correct`, `score`, `grader_output` are permanent (append-only, per `db/schema.sql`'s attempts table comment: *"Append-only"*), and `build_reveal` reconstructs the explanation live from the immutable `exercises.grading`/`exercises.explanation` JSONB columns on every `GET /v1/attempts/{id}` call.

---

## E. The streak + stats data

### backend/app/users/service.py — `get_stats`

```python
async def get_stats(db: AsyncSession, user_id: uuid.UUID) -> dict:
    stats = await db.get(UserStats, user_id)
    if stats is None:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "streak_freezes": 0,
            "total_attempts": 0,
            "total_correct": 0,
            "accuracy_by_type": {},
            "last_active_local_date": None,
        }
    return {
        "current_streak": stats.current_streak,
        "longest_streak": stats.longest_streak,
        "streak_freezes": stats.streak_freezes,
        "total_attempts": stats.total_attempts,
        "total_correct": stats.total_correct,
        "accuracy_by_type": project_accuracy(stats.accuracy_by_type),
        "last_active_local_date": (
            stats.last_active_local_date.isoformat() if stats.last_active_local_date else None
        ),
    }
```

Served at `GET /v1/me/stats`. So the profile endpoint returns: `current_streak`, `longest_streak`, `streak_freezes`, `total_attempts`, `total_correct`, `accuracy_by_type` (projected via `project_accuracy`), `last_active_local_date`. (`Profile.tsx` currently only *renders* `current_streak`, `longest_streak`, and `accuracy_by_type` — `streak_freezes`, `total_attempts`, `total_correct`, `last_active_local_date` are already in the payload but unused by the screen today.)

`GET /v1/me/concepts` (`get_concepts`) returns every `UserConceptState` row for the user, ordered by ascending mastery: `{concept, mastery, attempts, next_review_at}` — this is the "weakest concepts" source (`Profile.tsx` takes `.slice(0, 5)` of it, i.e. it already receives the *entire* concept list sorted weakest-first, not just a top-5, and truncates client-side).

### Is there a per-day activity history for a contribution-grid?

**No — read plainly.** `db/schema.sql`'s `user_stats` table (quoted in full below) stores only aggregate counters, no per-day series:

```sql
CREATE TABLE user_stats (
  user_id                uuid        PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  current_streak         int         NOT NULL DEFAULT 0,
  longest_streak         int         NOT NULL DEFAULT 0,
  last_active_local_date date,
  streak_freezes         int         NOT NULL DEFAULT 0,
  total_attempts         int         NOT NULL DEFAULT 0,
  total_correct          int         NOT NULL DEFAULT 0,
  accuracy_by_type       jsonb       NOT NULL DEFAULT '{}',
  updated_at             timestamptz NOT NULL DEFAULT now()
);
```

`streak_events` (also in `db/schema.sql`) is append-only and *does* have per-event `local_date`, but it only fires on a **streak transition** (`extended`/`reset`/`freeze_used`/`repaired`/`adjusted`) — see `backend/app/attempts/service.py::_update_streak_and_attempt_count`:

```python
if stats.last_active_local_date == today:
    # Already counted today: no streak transition, no StreakEvent row.
    await db.flush()
    return None
```

That means a day where the user was already active (a second session-open, or any day after the first attempt of that local day) writes **no** `streak_events` row — the table is one row per streak-changing day, not one row per active day, so it cannot be read directly as a daily activity log without risk of gaps (though in practice, since a fresh calendar day always causes exactly one transition — either `extended` or `reset` — `streak_events` rows *do* end up one-per-active-day in the common case; the gap only matters if `freeze_used`/`repaired`/`adjusted` semantics ever overlap a day already counted, which the code above explicitly prevents from double-writing).

The one table that unambiguously has one row per day-the-user-opened-the-app is `daily_sessions` (`db/schema.sql`):

```sql
CREATE TABLE daily_sessions (
  user_id       uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_date  date        NOT NULL,                -- user-local date
  exercise_list jsonb       NOT NULL,                -- [{exercise_id, version, slot, is_boss}]
  created_at    timestamptz NOT NULL DEFAULT now(),
  completed_at  timestamptz,
  PRIMARY KEY (user_id, session_date)
);
```

This is in fact exactly what `admin/service.py::compute_retention` already reads for D1/D7 retention (*"Uses daily_sessions... as the activity signal"*), confirming it is the intended source for "was the user active on date X." **So: a GitHub-style contribution grid is buildable from `daily_sessions` (one row per active day, `completed_at` distinguishes finished vs. opened-but-not-finished) — but there is no endpoint that exposes it today.** `GET /v1/me/stats` and `GET /v1/me/concepts` are the only user-facing reads, and neither touches `daily_sessions`. Building the grid needs a new endpoint (e.g. `GET /v1/me/activity?from=...&to=...`) that selects `session_date, completed_at` from `daily_sessions` for the user — straightforward given the table already exists and is already indexed by `(user_id, session_date)` as its primary key, but it does not exist yet.

### jobs/streak_recon.py

Read in full above (see raw Read output). It's a timezone-change repair job (`reconcile_streak_for_timezone_change`), not a daily-history builder — it only ever touches `user_stats.last_active_local_date` and writes a single `streak_events` row with `event='repaired'` when a timezone change would move the local-date boundary backward past an already-counted day. It confirms `streak_events.local_date` is the per-event date field but does not itself produce a daily grid.

---

## F. For the reviews feature (new)

### db/schema.sql (IN FULL)

```sql
-- ============================================================
-- Code Reading App : MVP Schema
-- Postgres 16+
-- Conventions:
--   * text + CHECK instead of enums (cheaper to migrate at MVP)
--   * timestamptz everywhere; user-local dates stored as date
--   * soft delete only on users; everything else is append/immutable
--   * all JSONB blobs are written by the server only, never by clients
-- ============================================================

CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

-- ------------------------------------------------------------
-- updated_at helper
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END $$ LANGUAGE plpgsql;

-- ============================================================
-- IDENTITY
-- ============================================================

CREATE TABLE users (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  username            citext      NOT NULL UNIQUE,          -- seeded from GitHub login
  display_name        text,
  avatar_url          text,
  timezone            text        NOT NULL DEFAULT 'UTC',   -- IANA name, validated in app
  level               text        NOT NULL DEFAULT 'mid'
                        CHECK (level IN ('junior','mid','senior')),
  onboarded           boolean     NOT NULL DEFAULT false,     -- set true by PATCH /me's level pick
  beta_allowed        boolean     NOT NULL DEFAULT false,     -- gates login/session access (M8)
  reminder_local_time time,                                  -- NULL = reminders off
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  deleted_at          timestamptz                            -- soft delete
);

CREATE TRIGGER trg_users_touch BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Provider-agnostic identities. MVP has exactly one row per user
-- (provider = 'github') but the shape is multi-provider from day one.
CREATE TABLE auth_identities (
  id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider           text        NOT NULL CHECK (provider IN ('github')),
  provider_user_id   text        NOT NULL,                  -- GitHub numeric id as text
  provider_login     text,                                  -- GitHub handle at link time
  access_token_enc   bytea,                                 -- AES-GCM sealed, key in KMS
  token_scopes       text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_user_id)
);

CREATE INDEX idx_auth_identities_user ON auth_identities (user_id);

-- Rotating opaque refresh tokens. family_id exists now (cheap) so the
-- post-MVP reuse-detection "kill the family" upgrade is a code change,
-- not a migration. MVP behavior on reuse: log + alert only.
CREATE TABLE refresh_tokens (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  family_id    uuid        NOT NULL,                 -- constant across rotations
  token_hash   bytea       NOT NULL UNIQUE,          -- sha256 of the opaque token
  issued_at    timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz NOT NULL,
  rotated_at   timestamptz,                          -- set when superseded
  revoked_at   timestamptz,                          -- logout / admin action
  user_agent   text,
  ip           inet
);

CREATE INDEX idx_refresh_tokens_user   ON refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_family ON refresh_tokens (family_id);

-- Beta allowlist (M8): an admin invites a GitHub handle here BEFORE that
-- person ever logs in; upsert_github_user() flips users.beta_allowed on the
-- matching row the moment they authenticate. Also the record of "who did we
-- invite", independent of whether they've shown up yet.
CREATE TABLE beta_invites (
  github_login citext      PRIMARY KEY,
  note         text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- CONTENT
-- ============================================================
-- Exercises are IMMUTABLE per (id, version). Fixing anything bumps
-- version. Serving picks the max live version per id.
-- payload  : what the client may see BEFORE answering
-- grading  : answer key / rubric. NEVER serialized to clients pre-answer.
-- explanation : revealed only in the grade response.

CREATE TABLE exercises (
  id                    uuid        NOT NULL,
  version               int         NOT NULL DEFAULT 1 CHECK (version >= 1),
  language              text        NOT NULL CHECK (language IN ('python')),
  type                  text        NOT NULL
                          CHECK (type IN ('spot_the_bug','trace','summarize','predict_the_fix')),
  grading_mode          text        NOT NULL
                          CHECK (grading_mode IN ('deterministic','rubric')),
  difficulty_authored   smallint    NOT NULL CHECK (difficulty_authored BETWEEN 1 AND 10),
  difficulty_empirical  numeric(4,2),                -- backfilled post-launch
  concepts              text[]      NOT NULL CHECK (cardinality(concepts) >= 1),
  tags                  text[]      NOT NULL DEFAULT '{}',
  est_time_s            int         NOT NULL DEFAULT 90,
  status                text        NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft','in_review','live','pulled','retired')),
  source                jsonb       NOT NULL,        -- origin/model/prompt_template_id/...
  payload               jsonb       NOT NULL,
  grading               jsonb       NOT NULL,
  explanation           jsonb       NOT NULL,
  validation_report_url text,                        -- s3:// pointer
  human_reviewed        boolean     NOT NULL DEFAULT false,
  created_at            timestamptz NOT NULL DEFAULT now(),
  validated_at          timestamptz,
  published_at          timestamptz,
  PRIMARY KEY (id, version)
);

-- Serving-path indexes
CREATE INDEX idx_exercises_serve
  ON exercises (language, type, status, difficulty_authored)
  WHERE status = 'live';
CREATE INDEX idx_exercises_concepts ON exercises USING gin (concepts);

-- Convenience: latest live version per exercise id
CREATE VIEW exercises_current AS
SELECT DISTINCT ON (id) *
FROM exercises
WHERE status = 'live'
ORDER BY id, version DESC;

-- ============================================================
-- DAILY SESSIONS
-- ============================================================
-- The durable record of "what was in your session today".
-- Redis caches it; if Redis flushes, we re-read this row instead of
-- re-sampling (users must not see a different session on re-open).

CREATE TABLE daily_sessions (
  user_id       uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_date  date        NOT NULL,                -- user-local date
  exercise_list jsonb       NOT NULL,                -- [{exercise_id, version, slot, is_boss}]
  created_at    timestamptz NOT NULL DEFAULT now(),
  completed_at  timestamptz,
  PRIMARY KEY (user_id, session_date)
);

-- ============================================================
-- ATTEMPTS  (hottest table; partitioned from day one)
-- ============================================================
-- Append-only. Rubric grading updates ONLY status/is_correct/score/
-- grader_output/graded_at on the same row (MVP simplification; splits
-- into grading_results post-MVP if the update contention ever shows).

CREATE TABLE attempts (
  id               bigint      GENERATED ALWAYS AS IDENTITY,
  user_id          uuid        NOT NULL REFERENCES users(id),
  exercise_id      uuid        NOT NULL,
  exercise_version int         NOT NULL,
  session_date     date        NOT NULL,             -- user-local date it counted toward
  answer           jsonb       NOT NULL,             -- shape depends on exercise type
  grading_mode     text        NOT NULL CHECK (grading_mode IN ('deterministic','rubric')),
  status           text        NOT NULL DEFAULT 'graded'
                     CHECK (status IN ('graded','grading_pending','grading_failed')),
  is_correct       boolean,                          -- NULL while rubric pending
  score            numeric(4,3) CHECK (score IS NULL OR (score >= 0 AND score <= 1)),
  grader_output    jsonb,                            -- rubric hits/misses, for the UI
  time_taken_ms    int,
  client           text        NOT NULL DEFAULT 'web' CHECK (client IN ('web','pwa')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  graded_at        timestamptz,
  PRIMARY KEY (id, created_at),                      -- partition key must be in PK
  FOREIGN KEY (exercise_id, exercise_version) REFERENCES exercises (id, version)
) PARTITION BY RANGE (created_at);

-- NOTE: uniqueness of Idempotency-Key is enforced in Redis (24h TTL),
-- not here; a partitioned unique constraint would have to include
-- created_at, which defeats it. Accepted MVP tradeoff: a replay after
-- Redis data loss inserts a duplicate, which the stats job dedupes.

CREATE INDEX idx_attempts_user ON attempts (user_id, created_at DESC);
CREATE INDEX idx_attempts_ex   ON attempts (exercise_id, exercise_version, created_at);

-- Bootstrap partitions + safety net. A monthly cron creates the next
-- partition; the DEFAULT partition guarantees inserts never fail if
-- the cron is missed (alert if it ever receives rows).
CREATE TABLE attempts_2026_07 PARTITION OF attempts
  FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE attempts_2026_08 PARTITION OF attempts
  FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE attempts_default PARTITION OF attempts DEFAULT;

-- ============================================================
-- PRECOMPUTED USER STATE  (nothing user-facing aggregates attempts live)
-- ============================================================

CREATE TABLE user_stats (
  user_id                uuid        PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  current_streak         int         NOT NULL DEFAULT 0,
  longest_streak         int         NOT NULL DEFAULT 0,
  last_active_local_date date,
  streak_freezes         int         NOT NULL DEFAULT 0,
  total_attempts         int         NOT NULL DEFAULT 0,
  total_correct          int         NOT NULL DEFAULT 0,
  accuracy_by_type       jsonb       NOT NULL DEFAULT '{}',
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_user_stats_touch BEFORE UPDATE ON user_stats
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Streaks are the retention crown jewel: every transition is audited
-- so any "my streak vanished" ticket is answerable in one query.
CREATE TABLE streak_events (
  id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  event       text        NOT NULL
                CHECK (event IN ('extended','reset','freeze_used','repaired','adjusted')),
  from_value  int         NOT NULL,
  to_value    int         NOT NULL,
  local_date  date        NOT NULL,
  note        text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_streak_events_user ON streak_events (user_id, created_at DESC);

-- Spaced repetition + skill graph state, keyed to the controlled
-- concept taxonomy (validated app-side against a versioned list).
CREATE TABLE user_concept_state (
  user_id        uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  concept        text        NOT NULL,
  mastery        numeric(4,3) NOT NULL DEFAULT 0 CHECK (mastery >= 0 AND mastery <= 1),
  attempts       int         NOT NULL DEFAULT 0,
  correct        int         NOT NULL DEFAULT 0,
  last_seen_at   timestamptz,
  next_review_at timestamptz,
  PRIMARY KEY (user_id, concept)
);

CREATE INDEX idx_ucs_due ON user_concept_state (user_id, next_review_at);

-- ============================================================
-- CONTENT FEEDBACK LOOP
-- ============================================================

-- Periodic job output; "only 31% caught this". App hides until n >= 30.
CREATE TABLE exercise_stats (
  exercise_id      uuid        NOT NULL,
  exercise_version int         NOT NULL,
  attempts_count   int         NOT NULL DEFAULT 0,
  correct_count    int         NOT NULL DEFAULT 0,
  solve_rate       numeric(4,3),
  median_time_ms   int,
  computed_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (exercise_id, exercise_version),
  FOREIGN KEY (exercise_id, exercise_version) REFERENCES exercises (id, version)
);

CREATE TABLE disputes (
  id               bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  exercise_id      uuid        NOT NULL,
  exercise_version int         NOT NULL,
  user_id          uuid        NOT NULL REFERENCES users(id),
  attempt_id       bigint,                           -- soft link (partitioned parent)
  reason           text        NOT NULL
                     CHECK (reason IN ('wrong_answer','ambiguous','broken_code',
                                       'bad_explanation','other')),
  body             text,
  status           text        NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open','accepted','rejected')),
  resolution_note  text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  resolved_at      timestamptz,
  FOREIGN KEY (exercise_id, exercise_version) REFERENCES exercises (id, version)
);

CREATE INDEX idx_disputes_open ON disputes (status, created_at) WHERE status = 'open';
CREATE INDEX idx_disputes_ex   ON disputes (exercise_id, exercise_version);

-- ============================================================
-- OPERATIONAL NOTES (not DDL)
-- ============================================================
-- * Redis owns: idempotency keys, OAuth state, rate limits, session cache.
-- * Attempt events additionally appended as JSONL to S3 (analytics later).
-- * Backups: daily base + WAL; restore drill BEFORE launch.
-- * Monthly cron: create next attempts partition; alert if attempts_default
--   ever has rows.
```

Note: `disputes` already exists and is conceptually adjacent to a "reviews" table — it's user-submitted, keyed to `(exercise_id, exercise_version)`, has a `status` lifecycle (`open`/`accepted`/`rejected`) and a `reason` CHECK-constrained enum. A new `reviews` table would likely want the same shape conventions: text+CHECK instead of a Postgres enum, `timestamptz` everywhere, FK to `(exercise_id, exercise_version)` composite, append/immutable except for a status/resolution flip.

### Migration template — backend/alembic/versions/0002_beta_allowlist.py (IN FULL)

```python
"""beta allowlist: users.beta_allowed + beta_invites

Revision ID: 0002_beta_allowlist
Revises: 0001_users_onboarded
Create Date: 2026-07-12 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_beta_allowlist"
down_revision: str | None = "0001_users_onboarded"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN beta_allowed boolean NOT NULL DEFAULT false")
    op.execute(
        """
        CREATE TABLE beta_invites (
          github_login citext      PRIMARY KEY,
          note         text,
          created_at   timestamptz NOT NULL DEFAULT now()
        )
        """,
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS beta_invites")
    op.execute("ALTER TABLE users DROP COLUMN beta_allowed")
```

Migrations are added as a new file in `backend/alembic/versions/`, named `NNNN_description.py`, with `revision`/`down_revision` wired to the prior file (current chain: `0000_schema_sql` → `0001_users_onboarded` → `0002_beta_allowlist` → `0003_predict_the_fix_type`), raw SQL via `op.execute(...)` rather than Alembic's autogenerate op helpers, and both `upgrade()` and `downgrade()` implemented.

### backend/app/admin/router.py (IN FULL)

```python
"""GET /admin/metrics: minimal ops dashboard (M7 observability).

Deliberately mounted OUTSIDE /v1 -- docs/05 section 7 reserves /admin/* for
a separate internal app behind its own auth, out of the public API
contract. Building that separate app/auth system is out of M7's scope; this
is a pragmatic placeholder gated by a shared-secret header instead (see
docs/07-decisions.md for the divergence entry), swappable for a real admin
app later without moving the public contract at all.
"""

from __future__ import annotations

import datetime as dt
import hmac

from fastapi import APIRouter, Depends, Header, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.service import collect_metrics, compute_retention
from app.auth.deps import DbSessionDep
from app.auth.service import invite_to_beta, revoke_beta_access
from app.config import get_settings
from app.core.errors import ApiError
from app.core.redis import get_redis
from app.schemas.admin import BetaInviteRequest

router = APIRouter(tags=["admin"])
RedisDep = Depends(get_redis)


def _require_admin_token(x_admin_token: str | None) -> None:
    configured = get_settings().ADMIN_METRICS_TOKEN
    if not configured:
        # No token configured: treat the endpoint as disabled rather than
        # silently open. 404, not 403 -- don't confirm the route exists.
        raise ApiError(404, "not_found", "Not found.")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, configured):
        raise ApiError(403, "forbidden", "Invalid admin token.")


@router.get("/admin/metrics")
async def admin_metrics(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    session: AsyncSession = DbSessionDep,
    redis: Redis = RedisDep,
) -> dict:
    _require_admin_token(x_admin_token)
    job_scheduler = getattr(request.app.state, "job_scheduler", None)
    return await collect_metrics(session, redis, job_scheduler)


@router.get("/admin/retention")
async def admin_retention(
    cohort_start: dt.date,
    offset_days: int = 1,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    session: AsyncSession = DbSessionDep,
) -> dict:
    _require_admin_token(x_admin_token)
    return await compute_retention(session, cohort_start, offset_days)


@router.post("/admin/beta/invite")
async def admin_beta_invite(
    payload: BetaInviteRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    session: AsyncSession = DbSessionDep,
) -> dict:
    _require_admin_token(x_admin_token)
    return await invite_to_beta(session, payload.github_login)


@router.post("/admin/beta/revoke")
async def admin_beta_revoke(
    payload: BetaInviteRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    session: AsyncSession = DbSessionDep,
) -> dict:
    _require_admin_token(x_admin_token)
    return await revoke_beta_access(session, payload.github_login)
```

**Existing admin endpoints:** `GET /admin/metrics` (golden signals + job health), `GET /admin/retention` (D1/Dn retention), `POST /admin/beta/invite`, `POST /admin/beta/revoke`.

**Auth:** a shared-secret header, `X-Admin-Token`, compared via `hmac.compare_digest` against `get_settings().ADMIN_METRICS_TOKEN`. If the token isn't configured, the route returns 404 (not 403) so it doesn't confirm its own existence. This matches HANDOFF.md's note: *"`/admin/metrics` uses a shared-secret token, not real auth (fine for a 20–30 person beta, flagged)."* The router docstring says `/admin/*` is deliberately mounted **outside** `/v1` because docs/05 section 7 reserves that prefix for a future separate internal app with its own auth — this is a pragmatic placeholder.

**Where an admin "read the reviews" view would live:** following this exact pattern, as a new `GET /admin/reviews` (or similar) in `backend/app/admin/router.py`, gated by the same `_require_admin_token`, backed by a new function in `backend/app/admin/service.py`. That mirrors how `admin_metrics`/`admin_retention` are both thin router functions delegating to `admin/service.py`.

`backend/app/schemas/admin.py` (in full):

```python
"""Admin-only request shapes (mounted outside /v1, D-73 pattern)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_STRICT = ConfigDict(extra="forbid")


class BetaInviteRequest(BaseModel):
    model_config = _STRICT

    github_login: str = Field(min_length=1)
```

### Does a user-model field exist for "this is the user's first completed session"?

**No — read plainly.** `backend/app/models/identity.py`'s `User` model (and the matching `users` table in `db/schema.sql`) has: `id, username, display_name, avatar_url, timezone, level, onboarded, beta_allowed, reminder_local_time, created_at, updated_at, deleted_at`. `onboarded` marks whether the level-pick screen was completed, not whether any session was finished. There is no `sessions_completed_count`, no `first_session_at`, nothing equivalent on `User` or `UserStats`.

What *could* answer "is this the user's first completed session" without a schema change: `daily_sessions` rows where `completed_at IS NOT NULL`, counted per user — `SELECT count(*) FROM daily_sessions WHERE user_id = :id AND completed_at IS NOT NULL`. A value of `1` at the moment a session just completed would mean "this was the first." `user_stats.total_attempts` is a weaker proxy (attempt-level, not session-level) and would overcount if a session has more than one exercise. Neither is precomputed or exposed via any current endpoint — both would need either a new admin/user query or a new column (e.g. `user_stats.sessions_completed` maintained alongside the existing counters in `attempts/service.py`) if this needs to be fast/frequent rather than a one-off COUNT.

---

## Summary of hard gaps found (for planning, not acted on)

1. **No daily activity/contribution-grid endpoint** — the data (`daily_sessions`) exists; the endpoint does not.
2. **No "review today's session" list endpoint** — `GET /v1/attempts/{id}` can serve a single reveal at any time after the fact, but nothing lists which attempt IDs belong to today's session.
3. **"I don't know" cannot be submitted today** — `validate_answer_shape` requires an exact key-set per type; a skip needs a new branch per type, not a relaxation.
4. **The scheduler cannot distinguish "wrong" from "declined"** — `update_concept_state(is_correct: bool, ...)` has no third state; skip vs. wrong would need a new interval constant and branch, and arguably a schema column, to diverge from `CONCEPT_INTERVAL_WRONG_DAYS`.
5. **No "first completed session" field** — derivable via a `COUNT` on `daily_sessions.completed_at`, but not stored or exposed anywhere.
6. **Admin auth is a shared secret, not real auth** — acknowledged and flagged already in HANDOFF.md; any new admin "reviews" view inherits this.
