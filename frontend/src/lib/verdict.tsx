import type { ReviewVerdict } from './types';

// Single source of truth for verdict -> copy/color, shared by the live
// session Reveal and the "review today's session" screen. `skipped` (and
// the two grading-in-flight states) render text-ink-muted -- never red/
// green, which are reserved exclusively for correctness (docs/08).
const COPY: Record<ReviewVerdict, string> = {
  correct: 'Correct.',
  incorrect: 'Incorrect.',
  skipped: 'Skipped.',
  grading_pending: 'Grading…',
  grading_failed: "Couldn't grade.",
};

const COLOR: Record<ReviewVerdict, string> = {
  correct: 'text-correct',
  incorrect: 'text-incorrect',
  skipped: 'text-ink-muted',
  grading_pending: 'text-ink-muted',
  grading_failed: 'text-ink-muted',
};

export function VerdictText({ verdict, className = '' }: { verdict: ReviewVerdict; className?: string }) {
  return <p className={`font-ui text-lg font-medium ${COLOR[verdict]} ${className}`}>{COPY[verdict]}</p>;
}
