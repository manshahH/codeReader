import { CodeBlock } from '../gutter/CodeBlock';
import type { SessionExercisePayload } from '../../lib/types';

interface Props {
  payload: SessionExercisePayload;
  selectedChoiceId: string | null;
  onSelectChoice: (id: string) => void;
}

export function TraceAnswer({ payload, selectedChoiceId, onSelectChoice }: Props) {
  return (
    <div className="flex flex-col gap-6">
      <CodeBlock code={payload.code} />
      {payload.question ? <p className="font-explanation text-lg text-ink">{payload.question}</p> : null}
      <fieldset className="flex flex-col gap-2">
        <legend className="sr-only">Choose an answer</legend>
        {(payload.choices ?? []).map((choice) => (
          <label
            key={choice.id}
            className={`flex cursor-pointer items-start gap-3 rounded-soft border px-4 py-3 font-code text-code transition-colors duration-fast ${
              selectedChoiceId === choice.id ? 'border-action bg-action-tint' : 'border-border'
            }`}
          >
            <input
              type="radio"
              name="choice"
              className="mt-1"
              checked={selectedChoiceId === choice.id}
              onChange={() => onSelectChoice(choice.id)}
            />
            <span>{choice.text}</span>
          </label>
        ))}
      </fieldset>
    </div>
  );
}
