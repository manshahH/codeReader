import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { AccuracyLine } from '../components/gutter/AccuracyLine';
import { ActivityHeatmap } from '../components/gutter/ActivityHeatmap';
import { GutterCell, StreakTicks } from '../components/gutter/Gutter';
import { EmailSection } from '../components/EmailSection';
import ReminderSection from '../components/ReminderSection';
import { ReviewPromptModal } from '../components/ReviewPromptModal';
import type { ReactNode } from 'react';

import {
  getMeAccuracyHistory,
  getMeActivity,
  getMeConcepts,
  getMeSessions,
  getMeStats,
  getReviewStatus,
} from '../lib/api';
import { useAuth } from '../lib/auth-context';
import { addDays, todayInTimezone } from '../lib/date';
import { formatRelativeDate, pluralizeDays } from '../lib/format';
import type { Panel } from '../lib/usePanel';
import { usePanel } from '../lib/usePanel';
import type {
  AccuracyHistoryDay,
  ActivityDay,
  ConceptMastery,
  MeSessionSummary,
  MeStats,
  ReviewStatusResponse,
} from '../lib/types';

const ACTIVITY_WINDOW_DAYS = 365;
const DEFAULT_CONCEPT_ROWS = 8;
const RECENT_SESSIONS_LIMIT = 50;
// How long a review stands before we ask again (spec: start at 14 days).
// Named so it's one place to tune, and easy to test by backdating a row's
// updated_at past this many days.
const REVIEW_AGAIN_THRESHOLD_DAYS = 14;

function daysSince(isoTimestamp: string): number {
  return (Date.now() - new Date(isoTimestamp).getTime()) / (1000 * 60 * 60 * 24);
}

function readable(concept: string): string {
  return concept.replace(/-/g, ' ');
}

function StreakSection({ stats }: { stats: MeStats }) {
  return (
    <section className="flex flex-col rounded-soft border border-border bg-surface-raised p-6 gap-3">
      <p className="text-sm text-ink-muted">Streak</p>
      <div className="flex items-end gap-8">
        <div>
          <p className="font-explanation text-3xl text-ink">{pluralizeDays(stats.current_streak)}</p>
          <p className="mt-1 text-xs text-ink-muted">current</p>
        </div>
        <div>
          <p className="font-explanation text-2xl text-ink-muted">{pluralizeDays(stats.longest_streak)}</p>
          <p className="mt-1 text-xs text-ink-muted">longest</p>
        </div>
        <div>
          <p className="font-explanation text-2xl text-ink-muted">{stats.total_sessions}</p>
          <p className="mt-1 text-xs text-ink-muted">sessions</p>
        </div>
      </div>
      <StreakTicks current={stats.current_streak} />
      {stats.streak_freezes > 0 ? (
        <p className="text-xs text-ink-muted">
          {stats.streak_freezes} freeze{stats.streak_freezes === 1 ? '' : 's'} available
        </p>
      ) : null}
    </section>
  );
}

function ActivitySection({ days, from, to }: { days: ActivityDay[]; from: string; to: string }) {
  return (
    <section className="flex flex-col rounded-soft border border-border bg-surface-raised p-6 lg:col-span-2">
      <p className="mb-3 text-sm text-ink-muted shrink-0">Activity, last {pluralizeDays(ACTIVITY_WINDOW_DAYS)}</p>
      <div className="shrink-0">
        <ActivityHeatmap days={days} from={from} to={to} />
      </div>
      <div className="mt-3 flex shrink-0 items-center gap-5 text-sm text-ink-muted">
        <span className="flex items-center gap-2">
          <GutterCell cellKey="legend-none" state="empty" /> No session
        </span>
        <span className="flex items-center gap-2">
          <GutterCell cellKey="legend-opened" state="tint" /> Opened
        </span>
        <span className="flex items-center gap-2">
          <GutterCell cellKey="legend-completed" state="filled" /> Completed
        </span>
      </div>
    </section>
  );
}

function AccuracySection({ accuracyByType }: { accuracyByType: Record<string, number> }) {
  const entries = Object.entries(accuracyByType);
  return (
    <section className="flex flex-col rounded-soft border border-border bg-surface-raised p-6 gap-3">
      <p className="text-sm text-ink-muted shrink-0">Accuracy by type</p>
      <div className="flex flex-col gap-2">
        {entries.length === 0 ? (
          <p className="text-sm text-ink-muted">No attempts yet.</p>
        ) : (
          entries.map(([type, accuracy]) => (
            <div key={type} className="flex shrink-0 items-center justify-between border-b border-border py-2">
              <span className="font-code text-sm capitalize text-ink">{type.replace(/_/g, ' ')}</span>
              <span className="font-code text-sm text-ink-muted">{Math.round(accuracy * 100)}%</span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function AccuracyHistorySection({ history }: { history: AccuracyHistoryDay[] }) {
  return (
    <section className="flex flex-col rounded-soft border border-border bg-surface-raised p-6 gap-3">
      <p className="text-sm text-ink-muted shrink-0">Average accuracy over time</p>
      <div>
        <AccuracyLine data={history} />
      </div>
    </section>
  );
}

function ConceptMasterySection({ concepts }: { concepts: ConceptMastery[] }) {
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? concepts : concepts.slice(0, DEFAULT_CONCEPT_ROWS);

  return (
    <section className="flex flex-col rounded-soft border border-border bg-surface-raised p-6 gap-3">
      <p className="text-sm text-ink-muted shrink-0">Needs review</p>
      <div className="flex flex-col gap-2">
        {shown.length === 0 ? (
          <p className="text-sm text-ink-muted">Not enough data yet.</p>
        ) : (
          shown.map((concept) => (
            <div key={concept.concept} className="flex shrink-0 items-center justify-between border-b border-border py-2">
              <span className="text-sm text-ink">{readable(concept.concept)}</span>
              <span className="flex items-center gap-3">
                <span className="font-code text-xs text-ink-muted">{formatRelativeDate(concept.next_review_at)}</span>
                <span className="font-code text-sm text-ink-muted">{Math.round(concept.mastery * 100)}%</span>
              </span>
            </div>
          ))
        )}
      </div>
      {concepts.length > DEFAULT_CONCEPT_ROWS ? (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="self-start shrink-0 text-sm text-ink-muted underline hover:text-ink"
        >
          {expanded ? 'Show fewer' : `Show all ${concepts.length}`}
        </button>
      ) : null}
    </section>
  );
}

function RecentSessionsSection({ sessions }: { sessions: MeSessionSummary[] }) {
  return (
    <section className="flex flex-col rounded-soft border border-border bg-surface-raised p-6 lg:col-span-2">
      <p className="mb-3 text-sm text-ink-muted shrink-0">Recent sessions</p>
      {sessions.length === 0 ? (
        <p className="text-sm text-ink-muted shrink-0">No sessions yet.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {sessions.map((entry) => (
            <div key={entry.session_date} className="flex shrink-0 flex-col gap-1 border-b border-border py-2">
              <div className="flex items-center justify-between">
                <span className="font-code text-sm text-ink">{entry.session_date}</span>
                <span className="font-code text-sm text-ink-muted">
                  {entry.completed ? `${entry.correct_count}/${entry.exercise_count}` : 'in progress'}
                  {entry.skipped_count > 0 ? ` · ${entry.skipped_count} skipped` : ''}
                </span>
              </div>
              {entry.concepts.length > 0 ? (
                <span className="text-xs text-ink-muted">{entry.concepts.map(readable).join(' · ')}</span>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function FallbackSection({
  label,
  text,
  className,
}: {
  label: string;
  text: string;
  className?: string;
}) {
  return (
    <section className={`flex flex-col rounded-soft border border-border bg-surface-raised p-6 gap-3 ${className ?? ''}`}>
      <p className="text-sm text-ink-muted shrink-0">{label}</p>
      <p className="text-sm text-ink-muted shrink-0">{text}</p>
    </section>
  );
}

// FIX-A: render a panel's real section when it loaded, else a same-labelled
// "loading"/"couldn't load" placeholder -- so one failed fetch degrades only
// its own section and the streak/activity/etc. that DID load still render.
function withPanel<T>(
  panel: Panel<T>,
  label: string,
  errorText: string,
  ok: (data: T) => ReactNode,
  className?: string,
): ReactNode {
  if (panel.status === 'ok') return ok(panel.data);
  return (
    <FallbackSection
      label={label}
      className={className}
      text={panel.status === 'loading' ? 'Loading…' : errorText}
    />
  );
}

export function Profile() {
  const [reviewStatus, setReviewStatus] = useState<ReviewStatusResponse | null>(null);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const to = todayInTimezone(user?.timezone ?? 'UTC');
  const from = addDays(to, -(ACTIVITY_WINDOW_DAYS - 1));

  const stats = usePanel<MeStats>(getMeStats);
  const concepts = usePanel<ConceptMastery[]>(getMeConcepts);
  const activity = usePanel<ActivityDay[]>(() => getMeActivity(from, to));
  const accuracyHistory = usePanel<AccuracyHistoryDay[]>(getMeAccuracyHistory);
  const sessions = usePanel<MeSessionSummary[]>(() => getMeSessions(RECENT_SESSIONS_LIMIT));

  const refetchReviewStatus = () => {
    // Best-effort throughout: a failed review-status fetch just hides the
    // "review again" affordance, it never blocks the profile.
    getReviewStatus()
      .then(setReviewStatus)
      .catch(() => undefined);
  };

  useEffect(() => {
    refetchReviewStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  // Never for a first-time reviewer -- reviewed must be true. Independent
  // of SessionComplete's first-session localStorage guard (a different
  // affordance entirely); no localStorage involved here at all.
  const showReviewAgain =
    reviewStatus?.reviewed === true &&
    reviewStatus.review !== null &&
    daysSince(reviewStatus.review.updated_at) >= REVIEW_AGAIN_THRESHOLD_DAYS;

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col gap-8 overflow-y-auto px-4 py-8 lg:px-8">
      <div className="flex shrink-0 items-center justify-between gap-4">
        <div>
          <p className="text-sm text-ink-muted">Signed in as</p>
          <p className="font-ui text-lg text-ink">{user?.display_name ?? user?.username}</p>
        </div>
        <div className="flex items-center gap-6">
          {showReviewAgain ? (
            <div className="flex items-center gap-3 hidden sm:flex">
              <p className="text-sm text-ink-muted">Been using this for a while?</p>
              <button
                type="button"
                onClick={() => setShowReviewModal(true)}
                className="rounded-soft border border-border px-4 py-2 text-sm font-medium text-ink transition-colors duration-fast hover:border-action hover:text-action"
              >
                Review us again
              </button>
            </div>
          ) : null}
          <button type="button" onClick={handleLogout} className="text-sm text-ink-muted underline hover:text-ink">
            Sign out
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {withPanel(
          activity,
          'Activity',
          'Couldn’t load activity.',
          (days) => <ActivitySection days={days} from={from} to={to} />,
          'lg:col-span-2',
        )}
        {withPanel(stats, 'Streak', 'Couldn’t load your streak.', (s) => <StreakSection stats={s} />)}
        {withPanel(stats, 'Accuracy by type', 'Couldn’t load accuracy.', (s) => (
          <AccuracySection accuracyByType={s.accuracy_by_type} />
        ))}
        {withPanel(accuracyHistory, 'Average accuracy over time', 'Couldn’t load history.', (h) => (
          <AccuracyHistorySection history={h} />
        ))}
        {withPanel(concepts, 'Needs review', 'Couldn’t load concepts.', (c) => (
          <ConceptMasterySection concepts={c} />
        ))}
        {/* NOT wrapped in withPanel and NOT a sixth usePanel call: this card
            reads the auth-context user, which is already loaded. Adding a sixth
            concurrent fetch here is the exact cause of the token-refresh race
            in docs/ops-incident-report-july-2026.md. */}
        <EmailSection />
        {/* A3 (D-137). Sits immediately after the email card because it is
            functionally downstream of having a confirmed address, and it reads
            the same already-loaded auth-context user for the same reason
            EmailSection does. Still no sixth fetch. */}
        <ReminderSection />
        {withPanel(
          sessions,
          'Recent sessions',
          'Couldn’t load recent sessions.',
          (s) => <RecentSessionsSection sessions={s} />,
          'lg:col-span-2',
        )}
      </div>


      {showReviewModal ? (
        <ReviewPromptModal
          onClose={() => setShowReviewModal(false)}
          onSubmitted={refetchReviewStatus}
          initialRating={reviewStatus?.review?.rating}
          initialBody={reviewStatus?.review?.body ?? ''}
        />
      ) : null}
    </div>
  );
}
