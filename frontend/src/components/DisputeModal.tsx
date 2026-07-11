import { useEffect, useState } from 'react';

import { ApiError, postDispute } from '../lib/api';
import type { DisputeReason } from '../lib/types';

interface Props {
  exerciseId: string;
  version: number;
  attemptId: number | null;
  onClose: () => void;
}

const REASONS: { id: DisputeReason; label: string }[] = [
  { id: 'wrong_answer', label: 'The marked answer looks wrong' },
  { id: 'ambiguous', label: 'The question is ambiguous' },
  { id: 'broken_code', label: 'The code itself is broken' },
  { id: 'bad_explanation', label: "The explanation doesn't hold up" },
  { id: 'other', label: 'Something else' },
];

export function DisputeModal({ exerciseId, version, attemptId, onClose }: Props) {
  const [reason, setReason] = useState<DisputeReason>('wrong_answer');
  const [body, setBody] = useState('');
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
    setStatus('submitting');
    setErrorMessage(null);
    try {
      await postDispute(exerciseId, version, { reason, body: body.trim() || null, attempt_id: attemptId });
      setStatus('done');
    } catch (err) {
      setStatus('error');
      setErrorMessage(err instanceof ApiError ? err.message : 'Could not send this. Try again.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-scrim p-0 sm:items-center sm:p-4" role="presentation" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Report a problem with this exercise"
        className="w-full max-w-md rounded-loose border border-border bg-surface-reading p-6"
        onClick={(event) => event.stopPropagation()}
      >
        {status === 'done' ? (
          <div className="flex flex-col gap-4">
            <p className="font-explanation text-lg text-ink">Report sent. Thanks for the check.</p>
            <button type="button" onClick={onClose} className="self-start text-sm text-action underline">
              Close
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="font-ui text-lg font-medium text-ink">Report a problem</h2>
              <button type="button" onClick={onClose} aria-label="Close" className="text-ink-muted hover:text-ink">
                ✕
              </button>
            </div>
            <fieldset className="flex flex-col gap-2">
              <legend className="sr-only">Reason</legend>
              {REASONS.map((option) => (
                <label key={option.id} className="flex items-center gap-2 text-sm text-ink">
                  <input
                    type="radio"
                    name="dispute-reason"
                    checked={reason === option.id}
                    onChange={() => setReason(option.id)}
                  />
                  {option.label}
                </label>
              ))}
            </fieldset>
            <textarea
              value={body}
              onChange={(event) => setBody(event.target.value)}
              placeholder="What did you notice? (optional)"
              rows={3}
              className="w-full rounded-soft border border-border bg-surface-reading p-3 text-sm text-ink outline-none focus-visible:border-action"
            />
            {errorMessage ? <p className="text-sm text-incorrect">{errorMessage}</p> : null}
            <div className="flex justify-end gap-3">
              <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-ink-muted">
                Cancel
              </button>
              <button
                type="button"
                onClick={submit}
                disabled={status === 'submitting'}
                className="rounded-soft bg-action px-4 py-2 text-sm font-medium text-surface-reading disabled:opacity-60"
              >
                {status === 'submitting' ? 'Sending…' : 'Send report'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
