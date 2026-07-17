import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { CodeBlock } from '../components/gutter/CodeBlock';
import {
  ExplanationSummary,
  PredictTheFixRevealView,
  SpotTheBugRevealView,
  TraceRevealView,
  getSpotTheBugCodeMarks,
} from '../components/session/revealViews';
import { SessionProgressRail } from '../components/session/SessionProgressRail';
import { ApiError, getSessionTodayReview } from '../lib/api';
import { VerdictText } from '../lib/verdict';
import type {
  Answer,
  PredictTheFixReveal,
  STBReveal,
  SessionExercise,
  SessionReviewExercise,
  SessionReviewResponse,
  SummarizeReveal,
  TraceReveal,
} from '../lib/types';

// Review-only: review rows carry no score/grader_output (unlike a live
// summarize attempt), so this is not shared with Reveal.tsx's
// SummarizeRevealView -- the data genuinely diverges, and forcing a shared
// shape here would overcomplicate both call sites.
function ReviewSummarizeRow({ code, reveal, answer }: { code: string; reveal: SummarizeReveal; answer: Answer }) {
  return (
    <div className="flex flex-col gap-4">
      {'text' in answer ? <p className="font-explanation text-base leading-relaxed text-ink">{answer.text}</p> : null}
      <ExplanationSummary summary={reveal.explanation.summary} principle={reveal.explanation.principle} />
    </div>
  );
}

function ReviewExerciseView({ row }: { row: SessionReviewExercise }) {
  const explanation = row.reveal && 'explanation' in row.reveal ? row.reveal.explanation : null;
  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 gap-10 lg:grid-cols-2">
      {/* Left Column: Code */}
      <div className="flex-1 overflow-y-auto pr-2">
        {row.reveal ? (
          (() => {
            let markLines;
            let notedLines;
            if (row.type === 'spot_the_bug') {
              const marks = getSpotTheBugCodeMarks(row.reveal as STBReveal, row.answer);
              markLines = marks.markLines;
              notedLines = marks.notedLines;
            }
            return <CodeBlock code={row.code} markLines={markLines} notedLines={notedLines} />;
          })()
        ) : (
          <CodeBlock code={row.code} />
        )}
      </div>

      {/* Right Column: Interaction */}
      <div className="flex-1 overflow-y-auto pr-2 flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <span className="font-code text-sm capitalize text-ink-muted">{row.type.replace(/_/g, ' ')}</span>
          <VerdictText verdict={row.verdict} className="text-base" />
        </div>
        <p className="text-sm text-ink-muted">{row.context_note}</p>

        {row.reveal ? (
          <>
            {row.type === 'spot_the_bug' ? (
              <SpotTheBugRevealView code={row.code} reveal={row.reveal as STBReveal} answer={row.answer} />
            ) : row.type === 'trace' ? (
              <TraceRevealView code={row.code} reveal={row.reveal as TraceReveal} answer={row.answer} />
            ) : row.type === 'predict_the_fix' ? (
              <PredictTheFixRevealView reveal={row.reveal as PredictTheFixReveal} answer={row.answer} />
            ) : (
              <ReviewSummarizeRow code={row.code} reveal={row.reveal as SummarizeReveal} answer={row.answer} />
            )}
            {row.type !== 'summarize' && explanation ? (
              <ExplanationSummary summary={explanation.summary} principle={explanation.principle} />
            ) : null}
          </>
        ) : (
          <p className="text-sm text-ink-muted">
            {row.verdict === 'grading_pending' ? 'Still grading — check back soon.' : "This one couldn't be graded."}
          </p>
        )}
      </div>
    </div>
  );
}

export function Review() {
  const [data, setData] = useState<SessionReviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    getSessionTodayReview()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load today’s review.'));
  }, []);

  if (error) return <p className="p-6 text-incorrect">{error}</p>;
  if (!data) return <p className="p-6 text-ink-muted">Loading…</p>;

  if (data.exercises.length === 0) {
    return (
      <div className="mx-auto flex h-full max-w-7xl flex-col gap-6 px-4 py-8">
        <p className="text-sm text-ink-muted">Review — {data.session_date}</p>
        <p className="text-ink-muted">
          Nothing to review yet today.{' '}
          <Link to="/session" className="underline hover:text-ink">
            Play today’s session
          </Link>
          .
        </p>
      </div>
    );
  }

  const row = data.exercises[currentIndex];
  const railExercises = data.exercises.map((e, i) => ({
    exercise_id: e.exercise_id,
    attempted: true,
    is_correct: e.verdict === 'correct',
    is_boss: false,
    slot: i + 1,
  })) as unknown as SessionExercise[];

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col gap-6 px-4 py-8">
      <div className="shrink-0 flex flex-col gap-6">
        <SessionProgressRail exercises={railExercises} currentIndex={currentIndex} />
        <div className="flex items-center justify-between text-sm text-ink-muted">
          <span>Review — {data.session_date}</span>
          <span className="font-code text-xs">
            {currentIndex + 1} / {data.exercises.length}
          </span>
        </div>
      </div>

      <ReviewExerciseView row={row} />

      <div className="flex shrink-0 items-center justify-between border-t border-border pt-4">
        <button
          type="button"
          disabled={currentIndex === 0}
          onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
          className="text-sm text-ink-muted underline hover:text-ink disabled:opacity-40 disabled:hover:text-ink-muted"
        >
          Previous
        </button>

        {currentIndex === data.exercises.length - 1 ? (
          <Link
            to="/"
            className="rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
          >
            Done
          </Link>
        ) : (
          <button
            type="button"
            onClick={() => setCurrentIndex((i) => Math.min(data.exercises.length - 1, i + 1))}
            className="rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
          >
            Next
          </button>
        )}
      </div>
    </div>
  );
}
