import { Link } from 'react-router-dom';

export function NavBar() {
  return (
    <header className="flex items-center justify-between px-4 py-3 md:pl-gutter-desktop md:pr-4">
      {/* D-131: NAVIGATION links carry the 44px touch floor. `inline-flex` +
          `items-center` grows the hit area around the text without moving the
          text itself, so the header's visual rhythm is unchanged and only the
          reachable area grows. Inline links inside prose deliberately do NOT
          get this -- padding them to 44px would break the reading measure that
          is the product. */}
      <Link to="/" className="inline-flex min-h-tap items-center font-explanation text-lg italic text-ink lg:min-h-0">
        Code Reader
      </Link>
      <div className="flex items-center gap-4">
        <Link
          to="/profile"
          className="inline-flex min-h-tap min-w-tap items-center justify-center text-sm text-ink-muted hover:text-ink lg:min-h-0 lg:min-w-0"
        >
          Profile
        </Link>
      </div>
    </header>
  );
}
