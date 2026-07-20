import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { confirmUnsubscribe, previewUnsubscribe } from '../lib/api';

/**
 * Landing screen for the unsubscribe link in a reminder or recap email
 * (A3, D-137(7)).
 *
 * PUBLIC. No RequireAuth and no AppLayout, unlike /verify-email. This is the
 * one screen in the app that must work for a signed-out person: the link is
 * opened from an inbox, possibly on a different device, and an unsubscribe that
 * bounces to GitHub OAuth is a broken unsubscribe. A broken unsubscribe is how
 * you get reported as spam instead, which costs the sending domain.
 *
 * MOUNTING DOES NOT UNSUBSCRIBE. The page previews what the token would turn
 * off and waits for a press. That asymmetry with /verify-email is deliberate:
 * a verification token is spent on arrival because the click IS the consent,
 * whereas here the mere fetch of a URL must not act. Mail clients, corporate
 * link scanners and prefetchers all follow links in email, and any of them
 * would otherwise silently unsubscribe someone who never clicked.
 *
 * The RFC 8058 one-click path is separate and does not come through this page:
 * a mail provider POSTs the List-Unsubscribe URL directly against the API.
 */

const LABEL: Record<string, string> = {
  reminder: 'daily reminders',
  recap: 'the weekly recap',
  all: 'all CodeReader email',
};

type State = 'loading' | 'ready' | 'done' | 'failed';

export function Unsubscribe() {
  const [params] = useSearchParams();
  const [state, setState] = useState<State>('loading');
  const [kind, setKind] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  // StrictMode double-invokes effects in dev. The preview is a read and would
  // be harmless twice, but guarding keeps one request per mount.
  const asked = useRef(false);

  const token = params.get('token');

  useEffect(() => {
    if (asked.current) return;
    asked.current = true;

    if (!token) {
      setState('failed');
      setMessage('That link is missing its unsubscribe code.');
      return;
    }

    previewUnsubscribe(token)
      .then((result) => {
        setKind(result.kind);
        setState('ready');
      })
      .catch(() => {
        setState('failed');
        setMessage('That unsubscribe link is not valid.');
      });
  }, [token]);

  const confirm = () => {
    if (!token) return;
    setBusy(true);
    confirmUnsubscribe(token)
      .then(() => setState('done'))
      .catch(() => {
        setState('failed');
        setMessage('That unsubscribe link is not valid.');
      })
      .finally(() => setBusy(false));
  };

  const what = kind ? (LABEL[kind] ?? 'these emails') : 'these emails';

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-4 py-8 lg:px-8">
      <section className="flex flex-col rounded-soft border border-border bg-surface-raised p-6 gap-3">
        <p className="text-sm text-ink-muted">Unsubscribe</p>

        {state === 'loading' ? <p className="text-sm text-ink">Loading…</p> : null}

        {state === 'ready' ? (
          <>
            <p className="text-sm text-ink">Turn off {what}?</p>
            <p className="text-xs text-ink-muted">
              This takes effect immediately and does not need you to sign in. You can turn
              it back on from your profile whenever you want.
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={confirm}
              className="self-start rounded-soft border border-border px-4 py-3 text-sm font-medium text-ink transition-colors duration-fast hover:border-action hover:text-action disabled:opacity-50 disabled:hover:border-border disabled:hover:text-ink"
            >
              {busy ? 'Turning off…' : `Turn off ${what}`}
            </button>
          </>
        ) : null}

        {state === 'done' ? (
          <>
            <p className="text-sm text-ink">Done. We will not send {what} again.</p>
            <p className="text-xs text-ink-muted">
              Your account and your streak are untouched. Turn this back on from your
              profile if you change your mind.
            </p>
          </>
        ) : null}

        {state === 'failed' ? (
          <p role="alert" className="text-sm text-ink">
            {message}
          </p>
        ) : null}

        <Link
          to="/profile"
          className="self-start text-sm text-ink-muted underline hover:text-ink"
        >
          Go to profile
        </Link>
      </section>
    </div>
  );
}
