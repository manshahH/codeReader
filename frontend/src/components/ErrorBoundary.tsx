import { Component, type ErrorInfo, type ReactNode } from 'react';
import * as Sentry from '@sentry/react';

interface Props {
  children: ReactNode;
  /** Rendered instead of the children after a descendant render throws. */
  fallback: ReactNode;
}

interface State {
  hasError: boolean;
}

/**
 * A render error anywhere below this boundary is caught here instead of
 * unmounting the whole React tree to a blank page. Two placements (main.tsx,
 * Session.tsx): one at the app root as the last-resort net, one around the
 * per-exercise session content (keyed by exercise index) so a single bad
 * exercise degrades to a "skip and continue" prompt rather than ending the
 * session. The error is still reported to Sentry (a no-op when no DSN is set,
 * same as initSentry), so turning a white-screen into a fallback never hides
 * the underlying bug.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    Sentry.captureException(error, {
      extra: { componentStack: info.componentStack },
    });
  }

  render(): ReactNode {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}

/** App-root fallback: a readable page with a way out, never a blank screen. */
export function FullPageErrorFallback() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-start gap-4 px-4 py-16">
      <h1 className="font-ui text-xl font-medium text-ink">Something went wrong.</h1>
      <p className="text-sm text-ink-muted">
        The app hit an unexpected error. Reloading usually fixes it — your streak and progress are
        safe.
      </p>
      <button
        type="button"
        onClick={() => window.location.assign('/')}
        className="rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
      >
        Reload
      </button>
    </div>
  );
}
