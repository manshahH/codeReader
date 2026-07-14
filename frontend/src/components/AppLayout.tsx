import type { ReactNode } from 'react';

import { NavBar } from './NavBar';

export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-surface-reading">
      <NavBar />
      <main className="flex-1 overflow-hidden">
        {children}
      </main>
    </div>
  );
}
