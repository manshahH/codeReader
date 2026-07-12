import { Navigate } from 'react-router-dom';

import { AppLayout } from '../components/AppLayout';
import { useAuth } from '../lib/auth-context';
import { Dashboard } from './Dashboard';

// Lands here after the GitHub OAuth callback (the backend redirects to
// APP_ORIGIN root, not /welcome -- see docs/07 divergence note) and on any
// direct visit to "/". AuthProvider has already attempted a silent refresh;
// this just routes on the result. "/" IS the dashboard for an onboarded
// user -- not a redirect to /session -- so entering the session player is
// always the user's own choice from there, never automatic.
export function RootGate() {
  const { status, user } = useAuth();

  if (status === 'loading') {
    return <p className="p-6 text-ink-muted">Loading…</p>;
  }
  if (status === 'unauthenticated' || !user) {
    return <Navigate to="/login" replace />;
  }
  if (!user.onboarded) {
    return <Navigate to="/onboarding" replace />;
  }
  return (
    <AppLayout>
      <Dashboard />
    </AppLayout>
  );
}
