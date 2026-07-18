import { useEffect, useRef, useState } from 'react';

import { ApiError, deleteEmail, resendEmailVerification, setEmail as apiSetEmail } from '../lib/api';
import { useAuth } from '../lib/auth-context';
import type { EmailState } from '../lib/types';

/**
 * A2 email capture on the Profile (docs/10; D-120).
 *
 * NO usePanel FETCH, deliberately. Profile already fires five concurrent calls
 * and that is the direct cause of the "Couldn't load..." token-refresh race in
 * docs/ops-incident-report-july-2026.md. Every field this card needs already
 * lives on the auth-context user, which POST /auth/refresh loaded before the
 * screen mounted, so a sixth call would buy nothing and cost the exact bug we
 * know about. Mutations return the same EmailState shape and are merged
 * straight back into that user.
 *
 * Design notes (anti-slop pre-flight): this is a sixth instance of the ONE
 * panel primitive the other five Profile sections use, not a new section type.
 * Every value comes from the existing semantic tokens; no new color, radius or
 * shadow is introduced, and there is no colored card edge, no gradient, no
 * icon, and no emoji. Addresses render in `font-code` because this app already
 * sets data in monospace and an address is a string the user has to proofread
 * character by character, which is the typo case the whole design guards.
 */

// Mirrors EMAIL_VERIFICATION_RESEND_COOLDOWN_S. The server is the authority and
// answers 429 with Retry-After; this only keeps the button from inviting a
// click that is already known to fail.
const RESEND_COOLDOWN_SECONDS = 60;

type Mode = 'idle' | 'editing';

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <section className="flex flex-col rounded-soft border border-border bg-surface-raised p-6 gap-3">
      <p className="text-sm text-ink-muted shrink-0">Email</p>
      {children}
    </section>
  );
}

function useCooldown(): [number, (seconds: number) => void] {
  const [remaining, setRemaining] = useState(0);
  const active = remaining > 0;
  const timer = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    if (!active) return;
    timer.current = setInterval(() => setRemaining((n) => Math.max(0, n - 1)), 1000);
    return () => clearInterval(timer.current);
  }, [active]);

  return [remaining, setRemaining];
}

export function EmailSection() {
  const { user, setUser } = useAuth();
  const [mode, setMode] = useState<Mode>('idle');
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cooldown, startCooldown] = useCooldown();

  if (!user) return null;

  const { email, email_verified: verified, pending_email: pending } = user;

  const apply = (next: EmailState) => {
    setUser({ ...user, ...next });
    setError(null);
  };

  const run = async (action: () => Promise<EmailState>, cooldownOnSuccess: boolean) => {
    setBusy(true);
    setError(null);
    try {
      apply(await action());
      if (cooldownOnSuccess) startCooldown(RESEND_COOLDOWN_SECONDS);
      setMode('idle');
      setDraft('');
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        // The server told us exactly how long to wait, so honour that over the
        // local guess.
        if (err.status === 429) startCooldown(err.retryAfterSeconds ?? RESEND_COOLDOWN_SECONDS);
      } else {
        setError('Something went wrong. Try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!draft.trim()) return;
    void run(() => apiSetEmail(draft.trim()), true);
  };

  const form = (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <label htmlFor="email-input" className="text-sm text-ink">
        {verified ? 'New address' : 'Email address'}
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <input
          id="email-input"
          type="email"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          autoComplete="email"
          placeholder="you@example.com"
          className="min-w-0 flex-1 rounded-soft border border-border bg-surface-reading px-3 py-2 font-code text-sm text-ink placeholder:text-ink-muted focus:border-action focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          className="rounded-soft border border-border px-4 py-2 text-sm font-medium text-ink transition-colors duration-fast hover:border-action hover:text-action disabled:opacity-50 disabled:hover:border-border disabled:hover:text-ink"
        >
          {busy ? 'Sending…' : 'Send confirmation link'}
        </button>
        {mode === 'editing' ? (
          <button
            type="button"
            onClick={() => {
              setMode('idle');
              setDraft('');
              setError(null);
            }}
            className="text-sm text-ink-muted underline hover:text-ink"
          >
            Cancel
          </button>
        ) : null}
      </div>
    </form>
  );

  // Four states, rendered as states rather than as a numbered sequence: a user
  // can arrive at any of them and none of them is "step 2 of 3".
  return (
    <Panel>
      {verified && email && mode === 'idle' ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="font-code text-sm text-ink">{email}</p>
          {/* Actions live here ONLY when nothing is pending. With a pending
              address the block below already owns "use a different address" and
              "remove", and showing both pairs would put two controls that do
              the same thing four inches apart. */}
          {pending ? null : (
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={() => setMode('editing')}
                className="text-sm text-ink-muted underline hover:text-ink"
              >
                Change
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void run(deleteEmail, false)}
                className="text-sm text-ink-muted underline hover:text-ink disabled:opacity-50"
              >
                Remove
              </button>
            </div>
          )}
        </div>
      ) : null}

      {!verified && !pending && mode === 'idle' ? (
        <>
          <p className="text-sm text-ink-muted">
            No address on file. Add one for daily reminders and your weekly recap. Nothing else.
          </p>
          {form}
        </>
      ) : null}

      {mode === 'editing' ? form : null}

      {pending ? (
        <div className="flex flex-col gap-2 border-t border-border pt-3">
          <p className="text-sm text-ink">
            Waiting on <span className="font-code">{pending}</span>
          </p>
          <p className="text-sm text-ink-muted">
            Open the link we sent to confirm it.{' '}
            {verified && email ? (
              <>
                Until then, reminders keep going to <span className="font-code">{email}</span>.
              </>
            ) : (
              'The link expires in 24 hours.'
            )}
          </p>
          <div className="flex items-center gap-4">
            <button
              type="button"
              disabled={busy || cooldown > 0}
              onClick={() => void run(resendEmailVerification, true)}
              className="text-sm text-ink-muted underline hover:text-ink disabled:no-underline disabled:opacity-50 disabled:hover:text-ink-muted"
            >
              {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend the link'}
            </button>
            {mode === 'idle' ? (
              <button
                type="button"
                onClick={() => setMode('editing')}
                className="text-sm text-ink-muted underline hover:text-ink"
              >
                Use a different address
              </button>
            ) : null}
            <button
              type="button"
              disabled={busy}
              onClick={() => void run(deleteEmail, false)}
              className="text-sm text-ink-muted underline hover:text-ink disabled:opacity-50"
            >
              {verified ? 'Remove email' : 'Cancel'}
            </button>
          </div>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="text-sm text-ink">
          {error}
        </p>
      ) : null}
    </Panel>
  );
}
