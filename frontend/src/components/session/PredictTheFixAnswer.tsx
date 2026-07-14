import { CodeBlock } from '../gutter/CodeBlock';
import type { SessionExercisePayload } from '../../lib/types';

interface Props {
  payload: SessionExercisePayload;
  selectedChoiceId: string | null;
  onSelectChoice: (id: string) => void;
}

// predict_the_fix (D-80): the user reads the buggy code and the failing test,
// then picks which candidate fix makes the test pass. Each choice is a full
// code diff, so choices render as code blocks rather than one-line radios.
export function PredictTheFixAnswer({ payload, selectedChoiceId, onSelectChoice }: Props) {
  return (
    <div className="flex flex-col gap-6">

      {payload.failing_test ? (
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium text-ink-muted">Failing test</p>
          <CodeBlock code={payload.failing_test} />
          {payload.test_output ? (
            <pre className="overflow-x-auto rounded-soft border border-incorrect/40 bg-incorrect-tint px-4 py-3 font-code text-code text-incorrect">
              {payload.test_output}
            </pre>
          ) : null}
        </div>
      ) : null}

      {payload.question ? <p className="font-explanation text-lg text-ink">{payload.question}</p> : null}

      <fieldset className="flex flex-col gap-3">
        <legend className="sr-only">Choose the fix that makes the test pass</legend>
        {(payload.choices ?? []).map((choice) => (
          <label
            key={choice.id}
            className={`flex cursor-pointer items-start gap-3 rounded-soft border p-3 transition-colors duration-fast ${
              selectedChoiceId === choice.id ? 'border-action bg-action-tint' : 'border-border'
            }`}
          >
            <input
              type="radio"
              name="fix"
              className="mt-3"
              checked={selectedChoiceId === choice.id}
              onChange={() => onSelectChoice(choice.id)}
            />
            <div className="min-w-0 flex-1">
              <CodeBlock code={choice.text} />
            </div>
          </label>
        ))}
      </fieldset>
    </div>
  );
}
