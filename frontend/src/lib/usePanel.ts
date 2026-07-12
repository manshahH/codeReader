import { useEffect, useState } from 'react';

// FIX-A: per-panel loading, so one failed fetch degrades ONLY its own panel and
// never blanks the whole page (the Dashboard/Profile `Promise.all` used to
// reject the entire load on any single 5xx). Each panel owns its own state and
// loads on its own timeline.
export type Panel<T> = { status: 'loading' } | { status: 'ok'; data: T } | { status: 'error' };

export function usePanel<T>(fetcher: () => Promise<T>): Panel<T> {
  const [state, setState] = useState<Panel<T>>({ status: 'loading' });
  useEffect(() => {
    let live = true;
    fetcher()
      .then((data) => {
        if (live) setState({ status: 'ok', data });
      })
      .catch(() => {
        if (live) setState({ status: 'error' });
      });
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return state;
}
