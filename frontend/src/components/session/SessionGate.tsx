import { StreakTicks } from '../gutter/Gutter';
import { pluralizeDays } from '../../lib/format';

interface Props {
  exerciseCount: number;
  currentStreak: number;
  onEnter: () => void;
}

// The calm entry screen before a session starts (product brief: entering is
// the user's choice, never an automatic drop into the player). Mirrors
// SessionComplete's bookend visual language -- font-explanation headline,
// StreakTicks, one primary action -- so the two ends of a session read as
// the same surface.
export function SessionGate({ exerciseCount, currentStreak, onEnter }: Props) {
  return (
    <div className="flex flex-col items-start gap-6 py-12">
      <p className="text-sm text-ink-muted">Your session is ready.</p>
      <h1 className="font-explanation text-3xl text-ink">
        {exerciseCount} {exerciseCount === 1 ? 'exercise' : 'exercises'} today.
      </h1>
      {currentStreak > 0 ? (
        <div className="flex items-center gap-3 text-ink-muted">
          <StreakTicks current={currentStreak} />
          <span>{pluralizeDays(currentStreak)} streak.</span>
        </div>
      ) : null}
      <button
        type="button"
        onClick={onEnter}
        className="rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
      >
        Enter sandbox
      </button>
    </div>
  );
}
