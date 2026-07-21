import { Link } from 'react-router-dom';

import { StreakReturn } from '../components/session/StreakReturn';
import { getMeConcepts, getMeSessions, getMeStats, getSessionToday } from '../lib/api';
import { useAuth } from '../lib/auth-context';
import { formatRelativeDate } from '../lib/format';
import type { Panel } from '../lib/usePanel';
import { usePanel } from '../lib/usePanel';
import type { ConceptMastery, MeSessionSummary, MeStats, SessionResponse } from '../lib/types';

const UPCOMING_REVIEWS_SHOWN = 5;

function timeOfDayGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Morning';
  if (hour < 18) return 'Afternoon';
  return 'Evening';
}

function readable(concept: string): string {
  return concept.replace(/-/g, ' ');
}

export function Dashboard() {
  const { user } = useAuth();
  const session = usePanel<SessionResponse>(getSessionToday);
  const concepts = usePanel<ConceptMastery[]>(getMeConcepts);
  const recentSessions = usePanel<MeSessionSummary[]>(() => getMeSessions(3));
  const stats = usePanel<MeStats>(getMeStats);

  const sessionData = session.status === 'ok' ? session.data : null;
  const total = sessionData?.exercises.length ?? 0;
  const doneCount = sessionData?.exercises.filter((e) => e.attempted).length ?? 0;
  const completed = sessionData?.completed ?? false;
  const todayConcepts = sessionData
    ? Array.from(new Set(sessionData.exercises.flatMap((e) => e.concepts)))
    : [];

  const todayState =
    session.status === 'loading'
      ? 'Loading today’s session…'
      : session.status === 'error'
        ? 'Couldn’t load today’s status. You can still start your session.'
        : total === 0
          ? 'Nothing to read just yet.'
          : completed
            ? 'Completed'
            : doneCount === 0
              ? 'Not started'
              : `In progress: ${doneCount} of ${total}`;

  // The primary CTA renders in every state except a confirmed empty pool, so a
  // failed secondary fetch -- or even a failed session fetch -- never blocks
  // the user from starting their session.
  const showCta = !(session.status === 'ok' && total === 0);

  return (
    // overflow-y-auto is load-bearing, not decoration: AppLayout's <main> is
    // overflow-hidden, so without a scroll container HERE anything past the
    // fold is simply unreachable. Profile.tsx has always had it; this screen
    // did not, and grew past the fold once A1 added the welcome-back panel.
    <div className="mx-auto flex h-full max-w-6xl flex-col gap-6 overflow-y-auto px-6 py-10">
      <header className="shrink-0">
        <p className="text-sm text-ink-muted">{timeOfDayGreeting()}</p>
        <h1 className="font-explanation text-3xl text-ink">{user?.display_name ?? user?.username}</h1>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 grid-rows-[auto_1fr] gap-x-10 gap-y-8 lg:grid-cols-2">
        {stats.status === 'ok' && stats.data.repair_restores_to !== null ? (
          <StreakReturn restoresTo={stats.data.repair_restores_to} className="shrink-0 lg:col-span-2" />
        ) : null}

        <section className="flex shrink-0 flex-col gap-4 rounded-loose bg-surface-raised p-7 lg:col-span-2">
          <p className="text-sm text-ink-muted">{todayState}</p>
          {showCta ? (
            <>
              <Link
                to={completed ? '/review' : '/session'}
                className="self-start rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
              >
                {completed ? "Review today's session" : 'Enter sandbox'}
              </Link>
              {todayConcepts.length > 0 ? (
                <p className="text-sm text-ink-muted">
                  Today covers: <span className="text-ink">{todayConcepts.map(readable).join(' · ')}</span>
                </p>
              ) : null}
              {/* A4's "peek at tomorrow" teaser moved to the session-complete
                  screen exclusively (D-143(3)): the finish moment is its home,
                  and showing it here too would repeat the same line seconds
                  later. The dashboard's "Upcoming reviews" panel still carries
                  the forward schedule. */}
            </>
          ) : (
            <p className="text-sm text-ink-muted">Check back in a little while.</p>
          )}
        </section>

        <section className="flex min-h-0 flex-col gap-3">
          <p className="shrink-0 text-sm text-ink-muted">Upcoming reviews</p>
          <div className="flex-1 overflow-y-auto pr-2">
            <UpcomingReviews panel={concepts} />
          </div>
        </section>

        <section className="flex min-h-0 flex-col gap-3">
          <p className="shrink-0 text-sm text-ink-muted">Recent sessions</p>
          <div className="flex-1 overflow-y-auto pr-2">
            <RecentSessions panel={recentSessions} />
          </div>
        </section>
      </div>
    </div>
  );
}

function PanelNote({ text }: { text: string }) {
  return <p className="text-sm text-ink-muted">{text}</p>;
}

function UpcomingReviews({ panel }: { panel: Panel<ConceptMastery[]> }) {
  if (panel.status === 'loading') return <PanelNote text="Loading…" />;
  if (panel.status === 'error') return <PanelNote text="Couldn’t load upcoming reviews." />;

  // Soonest due first -- "upcoming reviews" is honest, forward content
  // (unlike a preview of tomorrow's exercises, which the sampler hasn't
  // built yet and this app will not fake).
  const upcoming = [...panel.data]
    .filter((c) => c.next_review_at)
    .sort((a, b) => a.next_review_at.localeCompare(b.next_review_at))
    .slice(0, UPCOMING_REVIEWS_SHOWN);
  if (upcoming.length === 0) return <PanelNote text="Not enough data yet." />;
  return (
    <div className="flex flex-col gap-2">
      {upcoming.map((concept) => (
        <div key={concept.concept} className="flex items-center justify-between border-b border-border py-2">
          <span className="text-sm text-ink">{readable(concept.concept)}</span>
          <span className="font-code text-xs text-ink-muted">{formatRelativeDate(concept.next_review_at)}</span>
        </div>
      ))}
    </div>
  );
}

function RecentSessions({ panel }: { panel: Panel<MeSessionSummary[]> }) {
  if (panel.status === 'loading') return <PanelNote text="Loading…" />;
  if (panel.status === 'error') return <PanelNote text="Couldn’t load recent sessions." />;
  if (panel.data.length === 0) return <PanelNote text="No sessions yet." />;
  return (
    <div className="flex flex-col gap-2">
      {panel.data.map((entry) => (
        <div key={entry.session_date} className="flex flex-col gap-1 border-b border-border py-2">
          <div className="flex items-center justify-between">
            <span className="font-code text-sm text-ink">{entry.session_date}</span>
            <span className="font-code text-sm text-ink-muted">
              {entry.correct_count}/{entry.exercise_count}
              {entry.skipped_count > 0 ? ` · ${entry.skipped_count} skipped` : ''}
            </span>
          </div>
          {entry.concepts.length > 0 ? (
            <span className="text-xs text-ink-muted">{entry.concepts.map(readable).join(' · ')}</span>
          ) : null}
        </div>
      ))}
    </div>
  );
}
