import { Link } from 'react-router-dom';

import { useTheme } from '../lib/theme';

export function NavBar() {
  const [theme, toggleTheme] = useTheme();

  return (
    <header className="flex items-center justify-between border-b border-border px-4 py-3 md:pl-gutter-desktop md:pr-4">
      <Link to="/session" className="font-explanation text-lg italic text-ink">
        Code Reader
      </Link>
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
          className="text-sm text-ink-muted hover:text-ink"
        >
          {theme === 'light' ? 'Dark' : 'Light'}
        </button>
        <Link to="/profile" className="text-sm text-ink-muted hover:text-ink">
          Profile
        </Link>
      </div>
    </header>
  );
}
