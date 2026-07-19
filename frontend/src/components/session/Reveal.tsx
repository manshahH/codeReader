import { StreakTicks } from '../gutter/Gutter';
import { pluralizeDays } from '../../lib/format';
import { VerdictText } from '../../lib/verdict';
import {
  ExplanationSummary,
  PredictTheFixRevealView,
  SpotTheBugRevealView,
  TraceRevealView,
  getSpotTheBugDecorations,
} from './revealViews';
import { CodeBlock } from '../gutter/CodeBlock';
import { primaryDocuments } from '../../lib/code/model';
import type {
  Answer,
  AttemptResponse,
  PredictTheFixReveal,
  ReviewVerdict,
  STBReveal,
  SessionExercise,
  SummarizeReveal,
  TraceReveal,
} from '../../lib/types';

interface Props {
  exercise: SessionExercise;
  attempt: AttemptResponse;
  userAnswer: Answer;
  onNext: () => void;
  onDispute: () => void;
}

function PercentileLine({ percentile }: { percentile: AttemptResponse['percentile'] }) {
  if (!percentile) return null;
  const pct = Math.round(percentile.solve_rate * 100);
  return (
    <p className="text-sm text-ink-muted">
      {pct}% of readers caught this ({percentile.n} attempts).
    </p>
  );
}

function StreakLine({ streak }: { streak: AttemptResponse['streak'] }) {
  if (!streak) return null;
  return (
    <div className="flex items-center gap-3 text-sm text-ink-muted">
      <StreakTicks current={streak.current} />
      <span>
        {streak.event === 'extended'
          ? `Streak extended to ${pluralizeDays(streak.current)}.`
          : // A1: the return is the thing worth marking, not the loss. State
            // the new count as a fact and leave it there. No apology, no
            // "you lost your streak", nothing for the reader to feel bad about.
            `Welcome back. New streak: ${pluralizeDays(streak.current)}.`}
      </span>
    </div>
  );
}

function SummarizeRevealView({ attempt }: { attempt: AttemptResponse }) {
  const reveal = attempt.reveal as SummarizeReveal | null;
  return (
    <div className="flex flex-col gap-4">
      {attempt.score !== undefined && attempt.score !== null ? (
        <p className="text-sm text-ink-muted">Score: {Math.round(attempt.score * 100)}%</p>
      ) : null}
      {attempt.grader_output ? (
        <div className="flex flex-col gap-3">
          {attempt.grader_output.rubric_hits.length > 0 ? (
            <div>
              <p className="mb-1 text-sm font-medium text-correct">Covered</p>
              <ul className="list-inside list-disc text-sm text-ink-muted">
                {attempt.grader_output.rubric_hits.map((hit) => (
                  <li key={hit}>{hit}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {attempt.grader_output.rubric_misses.length > 0 ? (
            <div>
              <p className="mb-1 text-sm font-medium text-incorrect">Missed</p>
              <ul className="list-inside list-disc text-sm text-ink-muted">
                {attempt.grader_output.rubric_misses.map((miss) => (
                  <li key={miss}>{miss}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div>
            <p className="mb-1 text-sm text-ink-muted">Reference answer</p>
            <p className="font-explanation text-base leading-relaxed text-ink">{attempt.grader_output.reference_answer}</p>
          </div>
        </div>
      ) : null}
      {reveal?.explanation?.summary ? (
        <p className="font-explanation text-base leading-relaxed text-ink">{reveal.explanation.summary}</p>
      ) : null}
    </div>
  );
}

export function Reveal({ exercise, attempt, userAnswer, onNext, onDispute }: Props) {
  const explanation = attempt.reveal && 'explanation' in attempt.reveal ? attempt.reveal.explanation : null;
  // Within this component is_correct is null iff status === 'skipped':
  // grading_pending/grading_failed never reach Reveal (Session.tsx routes
  // them to their own phase branches before this renders).
  const verdict: ReviewVerdict = attempt.status === 'skipped' ? 'skipped' : attempt.is_correct ? 'correct' : 'incorrect';

  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 gap-10 lg:grid-cols-2">
      {/* Left Column: Code */}
      <div className="flex-1 overflow-y-auto pr-2">
        {(() => {
          const decorations =
            exercise.type === 'spot_the_bug' && attempt.reveal && 'correct_lines' in attempt.reveal
              ? getSpotTheBugDecorations(attempt.reveal as STBReveal, userAnswer)
              : [];
          return (
            <CodeBlock documents={primaryDocuments(exercise.payload)} decorations={decorations} />
          );
        })()}
      </div>

      {/* Right Column: Interaction */}
      <div className="flex-1 overflow-y-auto pr-2 flex flex-col gap-6">
        <VerdictText verdict={verdict} />

        {exercise.type === 'spot_the_bug' ? (
          <SpotTheBugRevealView
            code={exercise.payload.code}
            reveal={attempt.reveal as STBReveal}
            answer={userAnswer}
            reasonOptions={exercise.payload.reason_options ?? undefined}
          />
        ) : exercise.type === 'trace' ? (
          <TraceRevealView code={exercise.payload.code} reveal={attempt.reveal as TraceReveal} answer={userAnswer} />
        ) : exercise.type === 'predict_the_fix' ? (
          <PredictTheFixRevealView
            reveal={attempt.reveal as PredictTheFixReveal}
            answer={userAnswer}
            choices={exercise.payload.choices ?? undefined}
          />
        ) : (
          <SummarizeRevealView attempt={attempt} />
        )}

        {explanation && exercise.type !== 'summarize' ? (
          <ExplanationSummary summary={explanation.summary} principle={explanation.principle} />
        ) : null}

        <PercentileLine percentile={attempt.percentile} />
        <StreakLine streak={attempt.streak} />

        <div className="flex items-center justify-between gap-4 pt-2">
          <button type="button" onClick={onDispute} className="text-sm text-ink-muted underline hover:text-ink">
            Something wrong with this exercise?
          </button>
          <button
            type="button"
            onClick={onNext}
            className="rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
