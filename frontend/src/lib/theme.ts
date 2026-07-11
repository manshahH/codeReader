import { useEffect, useState } from 'react';

// Explicit toggle only, default light, no prefers-color-scheme auto-switch
// (docs/08b). This is a UI preference, not credentials, so localStorage is
// fine here -- unrelated to the access-token-in-memory-only rule.
const STORAGE_KEY = 'codereader:theme';

type Theme = 'light' | 'dark';

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme);
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === 'dark' ? 'dark' : 'light';
  });

  useEffect(() => {
    applyTheme(theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggle = () => setTheme((t) => (t === 'light' ? 'dark' : 'light'));
  return [theme, toggle];
}
