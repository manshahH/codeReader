import type { SessionExercisePayload } from '../../lib/types';

// D-129: `selectedLine`/`onSelectLine` used to be threaded in here and were
// never read -- the line is selected in the code gutter, which lives in the
// other column and is owned by Session. Dropped rather than restated as a
// range, so this component's interface says what it actually uses.
interface Props {
  payload: SessionExercisePayload;
  selectedReasonId: string | null;
  onSelectReason: (id: string) => void;
}

export function SpotTheBugAnswer({ payload, selectedReasonId, onSelectReason }: Props) {
  return (
    <div className="flex flex-col gap-6">
      {/* D-131: hidden below the breakpoint, where the answer sheet's own
          summary bar already says "Tap the line with the bug" -- and says it
          while the sheet is still resting, which is when the reader needs it.
          Repeating it inside the raised sheet told them to do the thing they
          had just done. Above the breakpoint there is no sheet and no summary
          bar, so this is the only place the instruction appears. */}
      <p className="mb-4 hidden font-medium text-action lg:block">Tap the line number in the code where the bug is.</p>
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
