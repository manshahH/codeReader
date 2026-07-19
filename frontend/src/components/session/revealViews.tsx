import { CodeBlock } from '../gutter/CodeBlock';
import { documentsFromCode, lineDecorations, type Decoration } from '../../lib/code/model';
import type {
  Answer,
  PredictTheFixReveal,
  ReasonOption,
  STBReveal,
  TraceChoice,
  TraceReveal,
} from '../../lib/types';

// Shared between the live session Reveal and the "review today's session"
// screen: both need the same code-marking/explanation logic against the
// same reveal shape, just sourced from different parent payloads
// (SessionExercise+AttemptResponse live vs. SessionReviewExercise after the
// fact). Narrowed to code/reveal/answer (+ optional choice-text lookups) so
// either caller can use them verbatim instead of re-deriving this logic.

/** Shown when a reveal payload is missing the fields a view needs (a graded
 * attempt whose `reveal` is null or partial). The session ErrorBoundary is the
 * hard net; this is the soft one, so a partial reveal reads as a plain note
 * instead of throwing. */
function RevealUnavailable() {
  return (
    <p className="text-sm text-ink-muted">
      The full explanation for this exercise isn’t available right now.
    </p>
  );
}

/**
 * D-129 decision 3: this returns DATA, not styling.
 *
 * It used to hand back a `Record<line, 'correct' | 'incorrect'>` plus a Set of
 * noted lines -- two shapes that only CodeBlock could interpret, and that could
 * only ever describe whole lines. It now returns a decoration list, so the same
 * function can describe a sub-expression mark the day an exercise type needs
 * one, and CodeBlock applies it without knowing where it came from.
 *
 * Empty list when the reveal is missing the fields it needs, which matches the
 * old undefined return: no marks rather than a throw.
 */
export function getSpotTheBugDecorations(reveal: STBReveal, answer: Answer): Decoration[] {
  if (!reveal.correct_lines || !reveal.explanation?.line_notes) return [];

  const decorations: Decoration[] = lineDecorations(reveal.correct_lines, 'correct');
  if ('line' in answer && !reveal.correct_lines.includes(answer.line)) {
    decorations.push(...lineDecorations([answer.line], 'incorrect'));
  }
  decorations.push(...lineDecorations(reveal.explanation.line_notes.map((n) => n.line), 'note'));
  return decorations;
}

export function ExplanationSummary({ summary, principle }: { summary: string; principle: string }) {
  return (
    <div className="measure flex flex-col gap-2 border-t border-border pt-4">
      <p className="font-explanation text-base leading-relaxed text-ink">{summary}</p>
      <p className="font-explanation text-sm italic leading-relaxed text-ink-muted">{principle}</p>
    </div>
  );
}

export function SpotTheBugRevealView({
  code,
  reveal,
  answer,
  reasonOptions,
}: {
  code: string;
  reveal: STBReveal;
  answer: Answer;
  reasonOptions?: ReasonOption[];
}) {
  if (!reveal?.correct_lines || !reveal.explanation?.line_notes) return <RevealUnavailable />;
  // This view renders the note LIST; the marks on the code itself are applied
  // by the caller, which owns the CodeBlock. It used to compute a markLines
  // record here too, which nothing read -- dead since the code column moved
  // out of this component. Removed rather than ported to decorations.
  const correctReasonText = reasonOptions?.find((r) => r.id === reveal.correct_reason_id)?.text;

  return (
    <div className="flex flex-col gap-4">
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

export function TraceRevealView({ code, reveal, answer }: { code: string; reveal: TraceReveal; answer: Answer }) {
  if (!reveal?.explanation?.trace_table || !reveal.explanation.why_wrong) return <RevealUnavailable />;
  const userChoiceId = 'choice_id' in answer ? answer.choice_id : null;
  const wrongNote = reveal.explanation.why_wrong.find((w) => w.choice_id === userChoiceId);

  return (
    <div className="flex flex-col gap-4">
      {wrongNote ? <p className="text-sm text-incorrect">{wrongNote.note}</p> : null}
      <div className="rounded-soft border border-border">
        <table className="w-full text-left font-code text-sm">
          <tbody>
            {reveal.explanation.trace_table.map((row, i) => (
              // Index, not row.line: a loop can revisit the same line more
              // than once, so line number alone isn't a unique key here.
              <tr key={i} className="border-b border-border last:border-0">
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

export function PredictTheFixRevealView({
  reveal,
  answer,
  choices,
}: {
  reveal: PredictTheFixReveal;
  answer: Answer;
  choices?: TraceChoice[];
}) {
  if (!reveal?.explanation?.why_wrong) return <RevealUnavailable />;
  const userChoiceId = 'choice_id' in answer ? answer.choice_id : null;
  const correctFix = choices?.find((c) => c.id === reveal.correct_choice_id)?.text;
  const wrongNote = reveal.explanation.why_wrong.find((w) => w.choice_id === userChoiceId);

  return (
    <div className="flex flex-col gap-4">
      {wrongNote ? <p className="text-sm text-incorrect">{wrongNote.note}</p> : null}
      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium text-correct">The fix that passes the test</p>
        {correctFix ? <CodeBlock documents={documentsFromCode(correctFix)} /> : null}
      </div>
    </div>
  );
}
