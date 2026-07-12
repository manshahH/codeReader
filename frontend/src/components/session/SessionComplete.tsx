import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { ReviewPromptModal } from '../ReviewPromptModal';
import { getMeActivity, getReviewStatus } from '../../lib/api';
import { useAuth } from '../../lib/auth-context';
import { addDays, todayInTimezone } from '../../lib/date';
import { StreakTicks } from '../gutter/Gutter';

interface Props {
  total: number;
  correct: number | null;
  currentStreak: number | null;
}

const REVIEW_PROMPT_SHOWN_KEY = 'codereader:reviewPromptShown';
// Short enough to keep the call light, long enough that a same-week repeat
// visit doesn't need a second network round trip beyond this one.
const ELIGIBILITY_WINDOW_DAYS = 7;

export function SessionComplete({ total, correct, currentStreak }: Props) {
  const { user } = useAuth();
  const [showReviewPrompt, setShowReviewPrompt] = useState(false);

  useEffect(() => {
    // session.first_completed_session only exists on the single POST
    // /attempts response that flips a session to complete -- it's gone on
    // reload. Re-derive "is this my first-ever completed session" instead,
    // from the same daily_sessions-backed data D-95's own definition uses:
    // exactly one completed:true entry recently means this is it. Survives
    // any reload for free. The localStorage flag is what actually enforces
    // "never shown twice" (it has to cover dismiss-without-submitting, which
    // the backend has no record of).
    if (localStorage.getItem(REVIEW_PROMPT_SHOWN_KEY)) return;
    const to = todayInTimezone(user?.timezone ?? 'UTC');
    const from = addDays(to, -(ELIGIBILITY_WINDOW_DAYS - 1));
    Promise.all([getMeActivity(from, to), getReviewStatus()])
      .then(([days, reviewStatus]) => {
        const completedCount = days.filter((d) => d.completed).length;
        if (completedCount === 1 && !reviewStatus.reviewed) setShowReviewPrompt(true);
      })
      .catch(() => {
        // Best-effort: a failed eligibility check just means no prompt this
        // sitting, never an error blown up onto the completion screen.
      });
  }, [user]);

  const dismissReviewPrompt = () => {
    localStorage.setItem(REVIEW_PROMPT_SHOWN_KEY, '1');
    setShowReviewPrompt(false);
  };

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
        to="/review"
        className="rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
      >
        Review today's session
      </Link>

      {showReviewPrompt ? <ReviewPromptModal onClose={dismissReviewPrompt} /> : null}
    </div>
  );
}
