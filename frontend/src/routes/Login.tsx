import { useSearchParams } from 'react-router-dom';

import { githubLoginUrl } from '../lib/api';

const ERROR_COPY: Record<string, string> = {
  oauth_state: 'That sign-in link expired. Try again.',
  oauth_denied: 'GitHub sign-in was cancelled.',
  // No `beta_required` entry while BETA_GATE_ENABLED is off (D-92, D-145 item 6):
  // the backend only emits ?error=beta_required when the gate is ON, so with it
  // off this beta-list copy is unreachable except by hand-typed URL. It falls
  // back to the generic message below. If the beta gate is re-enabled, restore a
  // specific entry here in the same change that flips the flag.
};

export function Login() {
  const [params] = useSearchParams();
  const error = params.get('error');

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-6">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="font-explanation text-3xl italic text-ink">Reedkode</h1>
        <p className="max-w-sm text-base text-ink-muted">
          A daily 5–10 minute session: read, trace, and judge real-looking code.
        </p>
      </div>
      {error ? <p className="text-sm text-incorrect">{ERROR_COPY[error] ?? 'Sign-in failed. Try again.'}</p> : null}
      <a
        href={githubLoginUrl()}
        className="rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
      >
        Continue with GitHub
      </a>
    </div>
  );
}
