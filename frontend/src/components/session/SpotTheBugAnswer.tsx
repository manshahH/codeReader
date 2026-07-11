import { CodeBlock } from '../gutter/CodeBlock';
import type { SessionExercisePayload } from '../../lib/types';

interface Props {
  payload: SessionExercisePayload;
  selectedLine: number | null;
  onSelectLine: (line: number) => void;
  selectedReasonId: string | null;
  onSelectReason: (id: string) => void;
}

export function SpotTheBugAnswer({ payload, selectedLine, onSelectLine, selectedReasonId, onSelectReason }: Props) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="mb-2 text-sm text-ink-muted">Tap the line number where the bug is.</p>
        <CodeBlock code={payload.code} selectedLine={selectedLine} onSelectLine={onSelectLine} />
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm text-ink-muted">Why is it a bug?</legend>
        {(payload.reason_options ?? []).map((option) => (
          <label
            key={option.id}
            className={`flex cursor-pointer items-start gap-3 rounded-soft border px-4 py-3 text-base transition-colors duration-fast ${
              selectedReasonId === option.id ? 'border-action bg-action-tint' : 'border-border'
            }`}
          >
            <input
              type="radio"
              name="reason"
              className="mt-1"
              checked={selectedReasonId === option.id}
              onChange={() => onSelectReason(option.id)}
            />
            <span>{option.text}</span>
          </label>
        ))}
      </fieldset>
    </div>
  );
}
