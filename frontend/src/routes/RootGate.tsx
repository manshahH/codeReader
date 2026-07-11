import { Navigate } from 'react-router-dom';

import { useAuth } from '../lib/auth-context';

// Lands here after the GitHub OAuth callback (the backend redirects to
// APP_ORIGIN root, not /welcome -- see docs/07 divergence note) and on any
// direct visit to "/". AuthProvider has already attempted a silent refresh;
// this just routes on the result.
export function RootGate() {
  const { status, user } = useAuth();

  if (status === 'loading') {
    return <p className="p-6 text-ink-muted">Loading…</p>;
  }
  if (status === 'unauthenticated' || !user) {
    return <Navigate to="/login" replace />;
  }
  return <Navigate to={user.onboarded ? '/session' : '/onboarding'} replace />;
}
