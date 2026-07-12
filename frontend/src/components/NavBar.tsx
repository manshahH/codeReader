import { Link } from 'react-router-dom';

export function NavBar() {
  return (
    <header className="flex items-center justify-between px-4 py-3 md:pl-gutter-desktop md:pr-4">
      <Link to="/" className="font-explanation text-lg italic text-ink">
        Code Reader
      </Link>
      <div className="flex items-center gap-4">
        <Link to="/profile" className="text-sm text-ink-muted hover:text-ink">
          Profile
        </Link>
      </div>
    </header>
  );
}
