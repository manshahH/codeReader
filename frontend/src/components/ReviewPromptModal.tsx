import { useEffect, useState } from 'react';

import { ApiError, postReview } from '../lib/api';
import { GutterCell } from './gutter/Gutter';

interface Props {
  onClose: () => void;
  onSubmitted?: () => void;
  initialRating?: number;
  initialBody?: string;
}

function RatingPicker({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <div className="flex items-center gap-2" role="radiogroup" aria-label="Rating, 1 to 5">
      {[1, 2, 3, 4, 5].map((n) => (
        <GutterCell
          key={n}
          cellKey={`rating-${n}`}
          state={n <= value ? 'filled' : 'empty'}
          onClick={() => onChange(n)}
          ariaLabel={`${n} of 5`}
        />
      ))}
    </div>
  );
}

// First-completed-session-ever prompt (D-96). Rating uses the gutter-tick
// vocabulary (five selectable GutterCells) rather than star icons, keeping
// the control inside the app's one repeated primitive family.
export function ReviewPromptModal({ onClose, onSubmitted, initialRating = 0, initialBody = '' }: Props) {
  const [rating, setRating] = useState(initialRating);
  const [body, setBody] = useState(initialBody);
  const [status, setStatus] = useState<'idle' | 'submitting' | 'done' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const submit = async () => {
    if (rating < 1) return;
    setStatus('submitting');
    setErrorMessage(null);
    try {
      await postReview({ rating, body: body.trim() || null });
      setStatus('done');
      onSubmitted?.();
    } catch (err) {
      setStatus('error');
      setErrorMessage(err instanceof ApiError ? err.message : 'Could not send this. Try again.');
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-scrim p-0 sm:items-center sm:p-4"
      role="presentation"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Rate Reedkode"
        className="w-full max-w-md rounded-loose border border-border bg-surface-reading p-6"
        onClick={(event) => event.stopPropagation()}
      >
        {status === 'done' ? (
          <div className="flex flex-col gap-4">
            <p className="font-explanation text-lg text-ink">Thanks — that helps.</p>
            <button type="button" onClick={onClose} className="self-start text-sm text-action underline">
              Close
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="font-ui text-lg font-medium text-ink">How's it going so far?</h2>
              <button type="button" onClick={onClose} aria-label="Close" className="text-ink-muted hover:text-ink">
                ✕
              </button>
            </div>
            <p className="text-sm text-ink-muted">
              Your review helps us improve it.
            </p>
            <RatingPicker value={rating} onChange={setRating} />
            <textarea
              value={body}
              onChange={(event) => setBody(event.target.value)}
              placeholder="Anything specific? (optional)"
              rows={3}
              className="w-full rounded-soft border border-border bg-surface-reading p-3 text-sm text-ink outline-none focus-visible:border-action"
            />
            {errorMessage ? <p className="text-sm text-incorrect">{errorMessage}</p> : null}
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={onClose}
                className="rounded-soft border border-border px-4 py-2 text-sm text-ink transition-colors duration-fast hover:border-action hover:text-action"
              >
                Not now
              </button>
              <button
                type="button"
                onClick={submit}
                disabled={status === 'submitting' || rating < 1}
                className="rounded-soft bg-action px-4 py-2 text-sm font-medium text-surface-reading disabled:opacity-60"
              >
                {status === 'submitting' ? 'Sending…' : 'Send'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
