import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

import { clearAccessToken, logout as apiLogout, refresh as apiRefresh } from './api';
import type { User } from './types';

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  setUser: (user: User) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const REFRESH_MARGIN_SECONDS = 60;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUserState] = useState<User | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setTimeout>>();

  const scheduleRefresh = useCallback((expiresInSeconds: number) => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    const delayMs = Math.max(0, (expiresInSeconds - REFRESH_MARGIN_SECONDS) * 1000);
    refreshTimer.current = setTimeout(() => {
      apiRefresh()
        .then((body) => {
          setUserState(body.user);
          scheduleRefresh(body.expires_in);
        })
        .catch(() => {
          setStatus('unauthenticated');
          setUserState(null);
        });
    }, delayMs);
  }, []);

  useEffect(() => {
    apiRefresh()
      .then((body) => {
        setUserState(body.user);
        setStatus('authenticated');
        scheduleRefresh(body.expires_in);
      })
      .catch(() => {
        setStatus('unauthenticated');
      });
    return () => {
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, [scheduleRefresh]);

  const setUser = useCallback((next: User) => {
    setUserState(next);
    setStatus('authenticated');
  }, []);

  const logout = useCallback(async () => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    await apiLogout();
    clearAccessToken();
    setUserState(null);
    setStatus('unauthenticated');
  }, []);

  return <AuthContext.Provider value={{ status, user, setUser, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
