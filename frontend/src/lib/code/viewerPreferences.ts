// Viewer preferences and the width breakpoint (D-130).
//
// Supersedes the write-only wrapPreference module from D-129, which stored a
// binary wrap/scroll with no way to say "whatever suits this width" and had no
// subscription, so nothing could re-render when it changed.
//
// Two preferences live here, both persisted per user (localStorage), and one
// piece of layout state (is the viewport narrow) that they depend on.

import { useCallback, useEffect, useSyncExternalStore } from 'react';

// --- the breakpoint ---------------------------------------------------------

/**
 * AVAILABLE WIDTH, not device class (D-130). No user-agent sniffing, no
 * pointer: coarse, no "is this a phone". The question the layout actually asks
 * is "is there room for two columns side by side", and that is a width.
 *
 * 1024px is where the session player's two-column grid starts (Tailwind `lg`),
 * so this constant and that breakpoint are the same line by construction. A
 * 667px landscape phone is therefore narrow -- correctly, since 667px cannot
 * hold code and answer controls side by side -- while still being a perfectly
 * good code-reading WIDTH, which is why the narrow layout gives the code the
 * full width rather than treating narrow as "small".
 */
export const WIDE_MIN_PX = 1024;
const WIDE_QUERY = `(min-width: ${WIDE_MIN_PX}px)`;

function subscribeToWidth(onChange: () => void): () => void {
  const mql = window.matchMedia(WIDE_QUERY);
  mql.addEventListener('change', onChange);
  return () => mql.removeEventListener('change', onChange);
}

/** True below the breakpoint. Drives the sequenced (mobile) arrangement. */
export function useIsNarrow(): boolean {
  return useSyncExternalStore(
    subscribeToWidth,
    () => !window.matchMedia(WIDE_QUERY).matches,
    // Server/first-paint fallback. Narrow is the safer default to render:
    // docs/08 is mobile-first, and a narrow tree on a wide screen reflows
    // correctly on the first effect, whereas the reverse can letterbox.
    () => true,
  );
}

// --- persisted preferences --------------------------------------------------

const WRAP_KEY = 'codereader.viewer.wrap';
const SCALE_KEY = 'codereader.viewer.codeScale';

/**
 * `auto` is the default and resolves BY WIDTH: wrap below the breakpoint,
 * scroll above it.
 *
 * That asymmetry is the D-130 resolution of the tension D-129 left open.
 * Horizontal scroll inside a 360px column is the problem being solved -- the
 * reader loses the left edge of every line and has to scrub back. On a wide
 * screen there is room for long lines, and scroll preserves the authored line
 * structure, which some developers prefer for diff-like reading. So neither
 * mode is globally right, and a single global default would be wrong at one
 * end. `wrap` and `scroll` are explicit user overrides that win everywhere.
 */
export type WrapPreference = 'auto' | 'wrap' | 'scroll';
export type WrapMode = 'wrap' | 'scroll';

export const DEFAULT_WRAP_PREFERENCE: WrapPreference = 'auto';

/** Clamped range for the code-size preference. Below 0.85 the code stops being
 * comfortably readable, which is the product; above 1.3 a 360px viewport fits
 * too few characters for the wrapping to help. */
export const CODE_SCALE_MIN = 0.85;
export const CODE_SCALE_MAX = 1.3;
export const CODE_SCALE_STEP = 0.15;
export const DEFAULT_CODE_SCALE = 1;

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    // Private browsing / storage disabled. The viewer still has to render.
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // The preference simply will not persist this session.
  }
}

// One subscription for both preferences. localStorage has no same-tab change
// event, so writes notify listeners directly; `storage` covers other tabs.
const listeners = new Set<() => void>();

function emit(): void {
  listeners.forEach((fn) => fn());
}

function subscribeToPreferences(onChange: () => void): () => void {
  listeners.add(onChange);
  window.addEventListener('storage', onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener('storage', onChange);
  };
}

export function readWrapPreference(): WrapPreference {
  const stored = readStorage(WRAP_KEY);
  return stored === 'wrap' || stored === 'scroll' ? stored : DEFAULT_WRAP_PREFERENCE;
}

export function writeWrapPreference(preference: WrapPreference): void {
  writeStorage(WRAP_KEY, preference);
  emit();
}

export function readCodeScale(): number {
  const parsed = Number.parseFloat(readStorage(SCALE_KEY) ?? '');
  if (!Number.isFinite(parsed)) return DEFAULT_CODE_SCALE;
  return Math.min(CODE_SCALE_MAX, Math.max(CODE_SCALE_MIN, parsed));
}

export function writeCodeScale(scale: number): void {
  writeStorage(SCALE_KEY, String(Math.min(CODE_SCALE_MAX, Math.max(CODE_SCALE_MIN, scale))));
  emit();
}

/** Resolve the stored preference against the current width. */
export function resolveWrapMode(preference: WrapPreference, isNarrow: boolean): WrapMode {
  if (preference === 'auto') return isNarrow ? 'wrap' : 'scroll';
  return preference;
}

export function useWrapPreference(): {
  preference: WrapPreference;
  mode: WrapMode;
  setPreference: (next: WrapPreference) => void;
} {
  const preference = useSyncExternalStore(subscribeToPreferences, readWrapPreference, () => DEFAULT_WRAP_PREFERENCE);
  const isNarrow = useIsNarrow();
  return {
    preference,
    mode: resolveWrapMode(preference, isNarrow),
    setPreference: useCallback((next: WrapPreference) => writeWrapPreference(next), []),
  };
}

export function useCodeScale(): { scale: number; setScale: (next: number) => void } {
  const scale = useSyncExternalStore(subscribeToPreferences, readCodeScale, () => DEFAULT_CODE_SCALE);

  // The scale is applied as a CSS custom property on the document root rather
  // than threaded through components, because --text-code is consumed by
  // Tailwind's `text-code` in a dozen places and they must all move together.
  useEffect(() => {
    document.documentElement.style.setProperty('--code-scale', String(scale));
  }, [scale]);

  return { scale, setScale: useCallback((next: number) => writeCodeScale(next), []) };
}
