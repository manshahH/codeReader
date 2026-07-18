import type { ReactNode } from 'react';
import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom';

import { AppLayout } from './components/AppLayout';
import { AuthProvider, useAuth } from './lib/auth-context';
import { Login } from './routes/Login';
import { Onboarding } from './routes/Onboarding';
import { Profile } from './routes/Profile';
import { Review } from './routes/Review';
import { RootGate } from './routes/RootGate';
import { Session } from './routes/Session';
import { VerifyEmail } from './routes/VerifyEmail';

function RequireAuth({
  children,
  requireOnboarded = true,
}: {
  children: ReactNode;
  requireOnboarded?: boolean;
}) {
  const { status, user } = useAuth();
  if (status === 'loading') return <p className="p-6 text-ink-muted">Loading…</p>;
  if (status === 'unauthenticated' || !user) return <Navigate to="/login" replace />;
  // Onboarding is a hard gate, not just the "/" landing: a deep-link straight
  // to /session (or /profile, /review) must not skip the level pick, or the
  // sampler runs with no level and its difficulty bands are undefined.
  if (requireOnboarded && !user.onboarded) return <Navigate to="/onboarding" replace />;
  return <>{children}</>;
}

function OnboardingRoute() {
  // Auth required, but onboarding NOT (requiring it here would loop). An
  // already-onboarded user has no reason to be on this screen -- send them to
  // their dashboard so they can't silently re-pick their level.
  const { status, user } = useAuth();
  if (status === 'loading') return <p className="p-6 text-ink-muted">Loading…</p>;
  if (status === 'unauthenticated' || !user) return <Navigate to="/login" replace />;
  if (user.onboarded) return <Navigate to="/" replace />;
  return <Onboarding />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RootGate />} />
      <Route path="/login" element={<Login />} />
      <Route path="/onboarding" element={<OnboardingRoute />} />
      <Route
        path="/session"
        element={
          <RequireAuth>
            <AppLayout>
              <Session />
            </AppLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/profile"
        element={
          <RequireAuth>
            <AppLayout>
              <Profile />
            </AppLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/review"
        element={
          <RequireAuth>
            <AppLayout>
              <Review />
            </AppLayout>
          </RequireAuth>
        }
      />
      {/* A2 (D-120): the target of the link in the verification email. Auth is
          required -- a token is scoped to the account it was issued for, so a
          signed-out click lands on /login and returns here after OAuth.
          Onboarding is NOT required: confirming an address is orthogonal to
          picking a level, and gating it would strand the user in a loop. */}
      <Route
        path="/verify-email"
        element={
          <RequireAuth requireOnboarded={false}>
            <AppLayout>
              <VerifyEmail />
            </AppLayout>
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
