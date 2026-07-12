import type { ReactNode } from 'react';

import { NavBar } from './NavBar';

export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-surface-reading">
      <NavBar />
      {children}
    </div>
  );
}
