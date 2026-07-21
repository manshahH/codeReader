import { Link, Navigate } from 'react-router-dom';

import { StreakReturn } from '../components/session/StreakReturn';
import { getMeStats, getSessionToday } from '../lib/api';
import { usePanel } from '../lib/usePanel';
import type { MeStats, SessionResponse, TomorrowTeaser } from '../lib/types';

function readable(concept: string): string {
  return concept.replace(/-/g, ' ');
}

/**
 * The session-complete screen (D-143). It is the redirect target of the last
 * exercise (Session.tsx), and the home for three things that had none: A1's
 * "celebrate the return" streak state, the first-completed warm cue, and A4's
 * "peek at tomorrow" teaser (relocated here exclusively, D-143(3)).
 *
 * Completion is derived from SERVER STATE, never navigation history (D-143(2)):
 * `GET /session/today.completed`. A user who reaches this route without a
 * completed session -- a deep-link, or tomorrow when today is fresh -- is sent
 * to the dashboard. Refresh re-fetches and re-guards, so it never renders blank.
 *
 * No new endpoint or field: it reads the same GET /session/today (completed +
 * teaser) and GET /me/stats (streak, repair) the dashboard already uses.
 */
export function SessionComplete() {
  const session = usePanel<SessionResponse>(getSessionToday);
  const stats = usePanel<MeStats>(getMeStats);

  if (session.status === 'loading') {
    return <CenteredNote text="Loading…" />;
  }
  if (session.status === 'error') {
    // Never blank on a failed fetch: a neutral page with a way home. We do not
    // assert completion we could not verify, so no celebration copy here.
    return (
      <Shell>
        <h1 className="font-explanation text-3xl text-ink">Nice work</h1>
        <p className="text-sm text-ink-muted">We couldn’t load the details of this session.</p>
        <BackToDashboard />
      </Shell>
    );
  }
  if (!session.data.completed) {
    // Guard: the screen is for a finished session only. Derived from the server,
    // so routing here directly cannot fake it.
    return <Navigate to="/" replace />;
  }

  const tomorrow = session.data.tomorrow;
  const streak = stats.status === 'ok' ? stats.data.current_streak : null;
  const restoresTo = stats.status === 'ok' ? stats.data.repair_restores_to : null;

  return (
    <Shell>
      <header className="flex flex-col gap-2">
        <h1 className="font-explanation text-3xl text-ink">Session complete</h1>
        <p className="text-sm text-ink-muted">That’s today’s reading done.</p>
      </header>

      {/* Streak: the A1 welcome-back + repair affordance when a reset is
          restorable (this is the half of A1 that was never built), otherwise a
          plain, non-nagging streak line. No guilt in either branch. */}
      {restoresTo !== null ? (
        <StreakReturn restoresTo={restoresTo} className="w-full" />
      ) : streak !== null && streak > 0 ? (
        <p className="text-sm text-ink-muted">
          You’re on a <span className="font-code text-ink">{streak}</span>-day streak.
        </p>
      ) : null}

      {tomorrow ? <TomorrowPeek teaser={tomorrow} /> : null}

      <div className="flex flex-col items-start gap-4 pt-2">
        <Link
          to="/"
          className="rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
        >
          Back to dashboard
        </Link>
        <Link
          to="/review"
          className="font-ui text-sm text-ink-muted transition-colors duration-fast hover:text-ink"
        >
          Review today’s session
        </Link>
      </div>
    </Shell>
  );
}

/**
 * A4 "peek at tomorrow" (D-142), relocated here from the dashboard (D-143(3)).
 * A single-concept forward hook, no guilt, no to-do-list count. Copy is a
 * schedule TEASE, not a promise (D-142 Addendum 3): "coming up for review"
 * states next_review_at, which this code owns, not the sampled set, which it
 * does not. The fallback variant (Addendum 5) makes NO date claim.
 */
function TomorrowPeek({ teaser }: { teaser: TomorrowTeaser }) {
  const concept = <span className="text-ink">{readable(teaser.concept)}</span>;
  return (
    <p className="text-sm text-ink-muted">
      {teaser.is_fallback ? (
        <>That’s your first day done. Next up: {concept}.</>
      ) : teaser.first_completed_session ? (
        <>That’s your first day done. {concept} is coming up for review tomorrow.</>
      ) : (
        <>Coming up for review tomorrow: {concept}.</>
      )}
    </p>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  // overflow-y-auto is load-bearing: AppLayout's <main> is overflow-hidden, so
  // without a scroll container here the content below the fold is unreachable
  // at short heights (the same fix Dashboard/Profile carry).
  return (
    <div className="mx-auto flex h-full max-w-xl flex-col gap-8 overflow-y-auto px-6 py-12">
      {children}
    </div>
  );
}

function BackToDashboard() {
  return (
    <Link
      to="/"
      className="self-start rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
    >
      Back to dashboard
    </Link>
  );
}

function CenteredNote({ text }: { text: string }) {
  return <p className="p-6 text-ink-muted">{text}</p>;
}
