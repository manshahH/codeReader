import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { verifyEmail } from '../lib/api';
import { useAuth } from '../lib/auth-context';

/**
 * Landing screen for the link in the verification email (A2, D-120).
 *
 * The token arrives in the query string and is spent immediately. It is never
 * written to state that outlives the call, never logged, and never put in a
 * link, so it does not leak through a Referer header on a later navigation.
 *
 * Every server-side failure -- unknown, expired, already used, superseded,
 * another account's token, or an address someone else confirmed first -- comes
 * back as one generic message, on purpose (D-120(5)). The screen does not try
 * to guess which happened; it says what the user can do about it, which is the
 * same thing in every case.
 */

type State = 'working' | 'done' | 'failed';

export function VerifyEmail() {
  const [params] = useSearchParams();
  const { user, setUser } = useAuth();
  const [state, setState] = useState<State>('working');
  const [message, setMessage] = useState('');
  const [address, setAddress] = useState<string | null>(null);
  // React 18 StrictMode double-invokes effects in dev, and this token is
  // single-use: without the guard the second call consumes nothing and reports
  // a failure over a success that already happened.
  const spent = useRef(false);

  const token = params.get('token');

  useEffect(() => {
    if (spent.current) return;
    spent.current = true;

    if (!token) {
      setState('failed');
      setMessage('That link is missing its confirmation code.');
      return;
    }

    verifyEmail(token)
      .then((next) => {
        setAddress(next.email);
        if (user) setUser({ ...user, ...next });
        setState('done');
      })
      .catch((err: unknown) => {
        setState('failed');
        setMessage(
          err instanceof Error && err.message
            ? err.message
            : 'That confirmation link is not valid or has expired.',
        );
      });
    // Runs once. `user` is intentionally not a dependency: re-running would
    // spend a second token.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col justify-center px-4 py-8 lg:px-8">
      <section className="flex flex-col rounded-soft border border-border bg-surface-raised p-6 gap-3">
        <p className="text-sm text-ink-muted">Email confirmation</p>

        {state === 'working' ? <p className="text-sm text-ink">Confirming…</p> : null}

        {state === 'done' ? (
          <>
            <p className="text-sm text-ink">
              {address ? (
                <>
                  Confirmed <span className="font-code">{address}</span>.
                </>
              ) : (
                'Confirmed.'
              )}
            </p>
            <p className="text-sm text-ink-muted">
              Reminders and your weekly recap will go here. You can change or remove it on your
              profile at any time.
            </p>
          </>
        ) : null}

        {state === 'failed' ? (
          <>
            <p role="alert" className="text-sm text-ink">
              {message}
            </p>
            <p className="text-sm text-ink-muted">
              Links expire after 24 hours, and asking for a new one replaces the old link. Send a
              fresh one from your profile.
            </p>
          </>
        ) : null}

        <Link
          to="/profile"
          className="self-start rounded-soft border border-border px-4 py-2 text-sm font-medium text-ink transition-colors duration-fast hover:border-action hover:text-action"
        >
          Go to profile
        </Link>
      </section>
    </div>
  );
}
