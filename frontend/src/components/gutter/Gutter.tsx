// The signature primitive (docs/08, docs/08b). Every place the app tracks
// position, progress, or history renders through this component: code line
// numbers, session progress dots, streak ticks, reveal annotation markers.
// Nothing else in the app invents its own "row of marks" layout.
import type { ReactNode } from 'react';

export type GutterCellState =
  | 'default'
  | 'muted'
  | 'selected'
  | 'correct'
  | 'incorrect'
  | 'boss'
  | 'filled'
  | 'tint'
  | 'empty';

export interface GutterCellProps {
  cellKey: string;
  label?: ReactNode;
  state?: GutterCellState;
  onClick?: () => void;
  ariaLabel?: string;
  title?: string;
}

const STATE_CLASSES: Record<GutterCellState, string> = {
  default: 'text-ink-muted',
  muted: 'text-ink-muted opacity-60',
  selected: 'text-action border border-action',
  correct: 'text-correct border border-correct',
  incorrect: 'text-incorrect border border-incorrect',
  boss: 'text-ink border border-ink-muted',
  filled: 'bg-action text-surface-reading',
  // Lighter fill than `filled`, no border -- the middle rung of a blue-
  // intensity ladder (D-99's contribution grid: hollow/tint/solid, all
  // --color-action, never green).
  tint: 'bg-action-tint text-action',
  empty: 'border border-border text-transparent',
};

export function GutterCell({ label, state = 'default', onClick, ariaLabel, title }: GutterCellProps) {
  const shared = `flex items-center justify-center rounded-tight font-code text-2xs leading-none transition-colors duration-fast ${STATE_CLASSES[state]}`;

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-label={ariaLabel}
        aria-pressed={state === 'selected'}
        title={title}
        className={`${shared} h-6 w-6 cursor-pointer hover:text-action hover:border hover:border-action focus-visible:text-action`}
      >
        {label}
      </button>
    );
  }

  return (
    <span aria-label={ariaLabel} title={title} className={`${shared} h-6 w-6`}>
      {label}
    </span>
  );
}

export function GutterRail({ cells, dense = false }: { cells: GutterCellProps[]; dense?: boolean }) {
  return (
    <div
      className={`flex flex-col items-start ${dense ? 'gap-1' : 'gap-2'}`}
      role={cells.some((c) => c.onClick) ? 'group' : undefined}
    >
      {cells.map((cell) => (
        <GutterCell key={cell.cellKey} {...cell} />
      ))}
    </div>
  );
}

export interface GutterLineButtonProps {
  line: number;
  state?: GutterCellState;
  onClick?: () => void;
  hasNote?: boolean;
  ariaLabel?: string;
}

const LINE_STATE_CLASSES: Record<GutterCellState, string> = {
  default: 'text-ink-muted',
  muted: 'text-ink-muted opacity-50',
  selected: 'text-action bg-action-tint',
  correct: 'text-correct bg-correct-tint',
  incorrect: 'text-incorrect bg-incorrect-tint',
  boss: 'text-ink',
  filled: 'text-action',
  tint: 'text-action bg-action-tint',
  empty: 'text-transparent',
};

/** A line number in the code gutter -- the exact spot spot_the_bug selection
 * happens (tap the number), and where reveal annotations anchor. */
export function GutterLineButton({ line, state = 'default', onClick, hasNote, ariaLabel }: GutterLineButtonProps) {
  const shared = `block w-full font-code text-code leading-relaxed tabular-nums text-right pr-3 transition-colors duration-fast ${LINE_STATE_CLASSES[state]}`;
  const content = (
    <>
      {line}
      {hasNote ? <span className="ml-1 text-action">•</span> : null}
    </>
  );
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-label={ariaLabel ?? `Select line ${line}`}
        aria-pressed={state === 'selected'}
        className={`${shared} cursor-pointer hover:text-action`}
      >
        {content}
      </button>
    );
  }
  return (
    <span aria-label={ariaLabel} className={shared}>
      {content}
    </span>
  );
}

/** A single filled/empty tick, used standalone for streak history and dots. */
export function GutterTick({ filled, label, boss }: { filled: boolean; label?: string; boss?: boolean }) {
  return (
    <span
      aria-label={label}
      title={label}
      className={`inline-block h-2 w-2 rounded-tick border ${
        filled ? (boss ? 'border-ink-muted bg-ink' : 'border-action bg-action') : 'border-border bg-transparent'
      }`}
    />
  );
}

const STREAK_TICK_CAP = 30;

/** Streak history = a column of gutter tick marks (docs/08), never a single
 * dot or a flame emoji. One filled tick per day of the current streak,
 * most recent last; capped so a long streak can't render an unbounded
 * column of DOM nodes. Shared by every place the app shows the streak
 * (session complete, profile). */
export function StreakTicks({ current }: { current: number }) {
  const shown = Math.min(Math.max(current, 1), STREAK_TICK_CAP);
  const overflow = Math.max(current - STREAK_TICK_CAP, 0);
  const ticks = Array.from({ length: shown }, (_, i) => i >= shown - current);
  return (
    <div className="flex flex-col items-start gap-1" aria-label={`${current}-day streak`}>
      {overflow > 0 ? <span className="font-code text-2xs text-ink-muted">+{overflow} earlier</span> : null}
      {ticks.map((filled, i) => (
        <GutterTick key={i} filled={filled} />
      ))}
    </div>
  );
}
