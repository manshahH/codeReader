import { useEffect, useRef, type ReactNode } from 'react';

/**
 * The two full-screen states of the narrow session player (D-134).
 *
 * REPLACES the bottom sheet. D-130's premise was "desktop separates in space,
 * mobile separates in time", but the sheet separated in SPACE after all -- code
 * above, controls below, competing for one screen. It only worked where there
 * happened to be room: at 375x667 and 400x670 the options clipped and the
 * submit button was unreachable, and predict_the_fix's options are entire code
 * blocks that were never going to fit beside anything.
 *
 * So: two states, each owning the whole viewport, with an explicit toggle.
 *
 * BOTH STATES STAY MOUNTED, stacked absolutely, with the inactive one hidden
 * via `visibility`. That is a deliberate choice and it is what makes the three
 * acceptance conditions hold:
 *   - scroll position survives a switch, because neither tree is unmounted and
 *     no layout is discarded (display:none would drop scroll offsets, and
 *     save/restore-by-ref races the first paint);
 *   - the transition is instant, because nothing reflows or re-renders -- it is
 *     a visibility flip, with no transform and no animation;
 *   - the code pane is never remounted, so it cannot re-run the measurement
 *     that D-133 showed can latch it shut.
 * The cost is that both trees render at once. They are small, and correctness
 * of the switch is worth more than the render.
 */
export interface NarrowSessionProps {
  mode: 'reading' | 'answering';
  /** The code, plus whatever the reading state pins beneath it. */
  reading: ReactNode;
  /** Always visible in the reading state, never inside the scroll region. */
  readingAction: ReactNode;
  /** Always visible in the answering state: the way back to the code. */
  answeringNav: ReactNode;
  /** The scrolling answer controls. */
  answering: ReactNode;
  /** Pinned to the bottom of the answering state, never after the options. */
  answeringSubmit: ReactNode;
}

function Pane({
  active,
  label,
  children,
}: {
  active: boolean;
  label: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);

  // `inert` is not a React 18 prop, so it is set on the node. Without it the
  // hidden state's controls stay in the tab order -- visibility:hidden removes
  // them from the a11y tree but a stale `inert` would not be enough on its own.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (active) el.removeAttribute('inert');
    else el.setAttribute('inert', '');
  }, [active]);

  return (
    <section
      ref={ref}
      aria-label={label}
      aria-hidden={!active}
      data-pane={label}
      data-active={active ? 'true' : 'false'}
      className={`absolute inset-0 flex flex-col ${active ? 'visible' : 'invisible pointer-events-none'}`}
    >
      {children}
    </section>
  );
}

export function NarrowSession({
  mode,
  reading,
  readingAction,
  answeringNav,
  answering,
  answeringSubmit,
}: NarrowSessionProps) {
  return (
    <div className="relative min-h-0 flex-1">
      <Pane active={mode === 'reading'} label="reading">
        {/* The code region grows; the action bar never scrolls away. */}
        <div className="flex min-h-0 flex-1 flex-col">{reading}</div>
        <div
          className="shrink-0 border-t border-border bg-surface-raised px-page py-2"
          style={{ paddingBottom: 'calc(var(--safe-bottom) + var(--space-2))' }}
        >
          {readingAction}
        </div>
      </Pane>

      <Pane active={mode === 'answering'} label="answering">
        {/* Pinned top: the way back to the code, visible at every scroll
            position because it is a sibling of the scroll region, not inside
            it. */}
        <div className="shrink-0 border-b border-border bg-surface-raised px-page py-2">{answeringNav}</div>

        {/* The only scrolling region in this state. */}
        <div data-answer-scroll className="min-h-0 flex-1 overflow-y-auto px-page py-3">
          {answering}
        </div>

        {/* Pinned bottom: submit is reachable without scrolling past the
            options, which is the failure that killed the sheet. */}
        <div
          className="shrink-0 border-t border-border bg-surface-raised px-page py-2"
          style={{ paddingBottom: 'calc(var(--safe-bottom) + var(--space-2))' }}
        >
          {answeringSubmit}
        </div>
      </Pane>
    </div>
  );
}

/**
 * The selected answer, pinned under the code while reading (D-134).
 *
 * A DELIBERATE docs/08 EXCEPTION, recorded rather than slipped in. docs/08 is
 * binding: "The session player is a single focused column: context note, code
 * (the hero of every screen), answer control, nothing else competing." This is
 * a fourth element in the reading state.
 *
 * The reasoning: trace asks you to compare candidate OUTPUTS against the code,
 * and that comparison is the exercise. Without this you must hold a 40-char
 * output string in working memory across a state switch, which is a memory
 * test, not a reading test. One row showing the candidate you are currently
 * testing turns the toggle into a verification pass over the code.
 *
 * Two limits keep it from becoming the sheet again: it renders ONLY once an
 * option is selected -- never as an empty bar on first read, when the reader
 * has nothing to verify and the code should be alone -- and it is one line,
 * clamped, not a panel.
 */
export function PinnedSelection({ label, value }: { label: string; value: string }) {
  return (
    <div
      data-pinned-selection
      className="shrink-0 border-t border-border bg-surface-raised px-page py-2"
    >
      <p className="text-2xs uppercase tracking-wide text-ink-muted">{label}</p>
      <p className="line-clamp-2 font-code text-xs text-ink">{value}</p>
    </div>
  );
}
