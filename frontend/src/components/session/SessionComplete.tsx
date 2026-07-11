import { Link } from 'react-router-dom';

import { GutterTick } from '../gutter/Gutter';

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
        <div className="flex items-center gap-2 text-ink-muted">
          <GutterTick filled label="streak" />
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
