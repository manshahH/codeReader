import { Link, Navigate } from 'react-router-dom';

import { StreakReturn } from '../components/session/StreakReturn';
import { getMeStats, getSessionToday } from '../lib/api';
import { usePanel } from '../lib/usePanel';
import type { MeStats, SessionResponse } from '../lib/types';

/**
 * The session-complete screen (D-143). It is the redirect target of the last
 * exercise (Session.tsx), and the home for A1's "celebrate the return" streak
 * state and the first-day acknowledgement.
 *
 * D-144: the A4 "peek at tomorrow" teaser moved to the Dashboard exclusively
 * (its evening impression is the value), and this screen owns its OWN first-day
 * state, read from the hoisted top-level `first_completed_session` rather than
 * from the teaser. That decouples the first-day moment from A4's fallback.
 *
 * Completion is derived from SERVER STATE, never navigation history (D-143(2)):
 * `GET /session/today.completed`. A user who reaches this route without a
 * completed session -- a deep-link, or tomorrow when today is fresh -- is sent
 * to the dashboard. Refresh re-fetches and re-guards, so it never renders blank.
 *
 * No new endpoint: it reads GET /session/today and GET /me/stats (streak,
 * repair), both already fetched by the dashboard.
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

  const isFirstSession = session.data.first_completed_session;
  const streak = stats.status === 'ok' ? stats.data.current_streak : null;
  const restoresTo = stats.status === 'ok' ? stats.data.repair_restores_to : null;

  return (
    <Shell>
      <header className="flex flex-col gap-2">
        <h1 className="font-explanation text-3xl text-ink">Session complete</h1>
        {isFirstSession ? (
          // D-144: the screen's own first-day state, decoupled from the teaser.
          // A plain acknowledgement -- no schedule claim (the teaser is on the
          // dashboard now), no guilt, no hype (docs/10 rule 2).
          <>
            <p className="text-sm text-ink">That was your first session.</p>
            <p className="text-sm text-ink-muted">
              One down. The habit is reading code you didn’t write, a little every day.
            </p>
          </>
        ) : (
          <p className="text-sm text-ink-muted">That’s today’s reading done.</p>
        )}
      </header>

      {/* Streak: the A1 welcome-back + repair affordance when a reset is
          restorable (this is the half of A1 that was never built), otherwise a
          plain, non-nagging streak line. No guilt in either branch. On a first
          session there is no streak history worth showing, so this is empty and
          the first-day copy above carries the moment. */}
      {restoresTo !== null ? (
        <StreakReturn restoresTo={restoresTo} className="w-full" />
      ) : streak !== null && streak > 0 ? (
        <p className="text-sm text-ink-muted">
          You’re on a <span className="font-code text-ink">{streak}</span>-day streak.
        </p>
      ) : null}

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
