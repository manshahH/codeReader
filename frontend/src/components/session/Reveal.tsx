import { CodeBlock } from '../gutter/CodeBlock';
import { GutterTick } from '../gutter/Gutter';
import type {
  Answer,
  AttemptResponse,
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

function VerdictBadge({ isCorrect }: { isCorrect: boolean | null }) {
  if (isCorrect === null) return null;
  return (
    <p className={`font-ui text-lg font-medium ${isCorrect ? 'text-correct' : 'text-incorrect'}`}>
      {isCorrect ? 'Correct.' : 'Incorrect.'}
    </p>
  );
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
    <div className="flex items-center gap-2 text-sm text-ink-muted">
      <GutterTick filled label="streak" />
      <span>
        {streak.event === 'extended' ? `Streak extended to ${streak.current} days.` : `Streak reset to ${streak.current}.`}
      </span>
    </div>
  );
}

function SpotTheBugReveal({ exercise, attempt, userAnswer }: { exercise: SessionExercise; attempt: AttemptResponse; userAnswer: Answer }) {
  const reveal = attempt.reveal as STBReveal;
  const markLines: Record<number, 'correct' | 'incorrect'> = {};
  reveal.correct_lines.forEach((line) => {
    markLines[line] = 'correct';
  });
  if ('line' in userAnswer && !reveal.correct_lines.includes(userAnswer.line)) {
    markLines[userAnswer.line] = 'incorrect';
  }
  const notedLines = new Set(reveal.explanation.line_notes.map((n) => n.line));
  const correctReasonText = exercise.payload.reason_options?.find((r) => r.id === reveal.correct_reason_id)?.text;

  return (
    <div className="flex flex-col gap-4">
      <CodeBlock code={exercise.payload.code} markLines={markLines} notedLines={notedLines} />
      {correctReasonText ? <p className="text-sm text-ink-muted">Reason: {correctReasonText}</p> : null}
      <ul className="flex flex-col gap-2">
        {reveal.explanation.line_notes.map((note) => (
          <li key={note.line} className="text-sm text-ink-muted">
            <span className="font-code text-action">Line {note.line}</span> — {note.note}
          </li>
        ))}
      </ul>
    </div>
  );
}

function TraceRevealView({ exercise, attempt, userAnswer }: { exercise: SessionExercise; attempt: AttemptResponse; userAnswer: Answer }) {
  const reveal = attempt.reveal as TraceReveal;
  const userChoiceId = 'choice_id' in userAnswer ? userAnswer.choice_id : null;
  const wrongNote = reveal.explanation.why_wrong.find((w) => w.choice_id === userChoiceId);

  return (
    <div className="flex flex-col gap-4">
      <CodeBlock code={exercise.payload.code} />
      {wrongNote ? <p className="text-sm text-incorrect">{wrongNote.note}</p> : null}
      <div className="rounded-soft border border-border">
        <table className="w-full text-left font-code text-sm">
          <tbody>
            {reveal.explanation.trace_table.map((row) => (
              <tr key={row.line} className="border-b border-border last:border-0">
                <td className="px-3 py-2 text-ink-muted">L{row.line}</td>
                <td className="px-3 py-2 text-ink">{row.state}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SummarizeRevealView({ attempt }: { attempt: AttemptResponse }) {
  const reveal = attempt.reveal as SummarizeReveal;
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
      <p className="font-explanation text-base leading-relaxed text-ink">{reveal.explanation.summary}</p>
    </div>
  );
}

export function Reveal({ exercise, attempt, userAnswer, onNext, onDispute }: Props) {
  const explanation = attempt.reveal && 'explanation' in attempt.reveal ? attempt.reveal.explanation : null;

  return (
    <div className="flex flex-col gap-6">
      <VerdictBadge isCorrect={attempt.is_correct} />

      {exercise.type === 'spot_the_bug' ? (
        <SpotTheBugReveal exercise={exercise} attempt={attempt} userAnswer={userAnswer} />
      ) : exercise.type === 'trace' ? (
        <TraceRevealView exercise={exercise} attempt={attempt} userAnswer={userAnswer} />
      ) : (
        <SummarizeRevealView attempt={attempt} />
      )}

      {explanation && exercise.type !== 'summarize' ? (
        <div className="measure flex flex-col gap-2 border-t border-border pt-4">
          <p className="font-explanation text-base leading-relaxed text-ink">{explanation.summary}</p>
          <p className="font-explanation text-sm italic leading-relaxed text-ink-muted">{explanation.principle}</p>
        </div>
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
  );
}
