import { useState } from 'react';

import { repairStreak } from '../../lib/api';

/**
 * A1 "celebrate the return" (docs/10; D-116), shared by the Dashboard and the
 * session-complete screen (D-143). Renders only while a repair is actually
 * available, so it appears at most once per reset and disappears the moment it
 * is used. Deliberately quieter than a primary CTA: a bordered panel, so
 * returning reads as an offer and never outranks the day's session. One
 * affordance, no countdown, no reminder to come back, no guilt.
 *
 * Layout-neutral: the caller passes `className` for its own grid/width. Copy
 * strings are unchanged from the original Dashboard WelcomeBack so
 * streak-welcome-back.spec.ts still pins them.
 */
export function StreakReturn({ restoresTo, className = '' }: { restoresTo: number; className?: string }) {
  const [state, setState] = useState<'offer' | 'working' | 'done' | 'gone'>('offer');
  const [restored, setRestored] = useState(0);

  if (state === 'gone') return null;

  async function repair() {
    setState('working');
    try {
      const result = await repairStreak(crypto.randomUUID());
      setRestored(result.current_streak);
      setState('done');
    } catch {
      // A 409 means the offer expired or was already used. Nothing was lost
      // and there is nothing for the reader to fix, so retire it quietly.
      setState('gone');
    }
  }

  return (
    <section className={`flex flex-col items-start gap-3 rounded-loose border border-border p-6 ${className}`}>
      {state === 'done' ? (
        <p className="text-sm text-ink">
          Restored. Your streak is back at{' '}
          <span className="font-code">{restored}</span> {restored === 1 ? 'day' : 'days'}.
        </p>
      ) : (
        <>
          <p className="text-sm text-ink">Good to see you again.</p>
          <p className="text-sm text-ink-muted">
            You can pick your previous streak back up, or just start a new one today. Either way
            works.
          </p>
          <button
            type="button"
            onClick={repair}
            disabled={state === 'working'}
            className="rounded-soft border border-border px-4 py-2 font-ui text-sm text-ink transition-colors duration-fast hover:bg-surface-raised disabled:opacity-60"
          >
            {state === 'working' ? 'Restoring…' : `Restore your ${restoresTo}-day streak`}
          </button>
        </>
      )}
    </section>
  );
}
