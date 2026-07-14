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
import { ApiError, getSessionTodayReview } from '../lib/api';
import { VerdictText } from '../lib/verdict';
import type {
  Answer,
  PredictTheFixReveal,
  STBReveal,
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

function ReviewRow({ row }: { row: SessionReviewExercise }) {
  const explanation = row.reveal && 'explanation' in row.reveal ? row.reveal.explanation : null;
  return (
    <div className="flex flex-col gap-4 border-b border-border py-6 last:border-0">
      <div className="flex items-center justify-between">
        <span className="font-code text-sm capitalize text-ink-muted">{row.type.replace(/_/g, ' ')}</span>
        <VerdictText verdict={row.verdict} className="text-base" />
      </div>
      <p className="text-sm text-ink-muted">{row.context_note}</p>

      {row.reveal ? (
        <>
          {(() => {
            let markLines;
            let notedLines;
            if (row.type === 'spot_the_bug') {
              const marks = getSpotTheBugCodeMarks(row.reveal as STBReveal, row.answer);
              markLines = marks.markLines;
              notedLines = marks.notedLines;
            }
            return <CodeBlock code={row.code} markLines={markLines} notedLines={notedLines} />;
          })()}
          
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
        <>
          <CodeBlock code={row.code} />
          <p className="text-sm text-ink-muted">
            {row.verdict === 'grading_pending' ? 'Still grading — check back soon.' : "This one couldn't be graded."}
          </p>
        </>
      )}
    </div>
  );
}

export function Review() {
  const [data, setData] = useState<SessionReviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSessionTodayReview()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load today’s review.'));
  }, []);

  if (error) return <p className="p-6 text-incorrect">{error}</p>;
  if (!data) return <p className="p-6 text-ink-muted">Loading…</p>;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 px-4 py-8">
      <p className="text-sm text-ink-muted">Review — {data.session_date}</p>
      {data.exercises.length === 0 ? (
        <p className="text-ink-muted">
          Nothing to review yet today.{' '}
          <Link to="/session" className="underline hover:text-ink">
            Play today’s session
          </Link>
          .
        </p>
      ) : (
        <>
          <div className="flex flex-col">
            {data.exercises.map((row) => (
              <ReviewRow key={row.exercise_id} row={row} />
            ))}
          </div>
          <Link
            to="/"
            className="self-start rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
          >
            Done
          </Link>
        </>
      )}
    </div>
  );
}
