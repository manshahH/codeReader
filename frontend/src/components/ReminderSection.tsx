import { useState } from 'react';

import { ApiError, patchEmailPrefs, patchMe } from '../lib/api';
import { useAuth } from '../lib/auth-context';
import type { EmailPrefs } from '../lib/types';

/**
 * A3 reminder + weekly recap controls on the Profile (docs/10; D-137).
 *
 * NO usePanel FETCH, for the same reason EmailSection has none: Profile already
 * fires five concurrent calls and that is the direct cause of the "Couldn't
 * load..." token-refresh race in docs/ops-incident-report-july-2026.md.
 * `reminder_local_time` and `email_prefs` both ride on the auth-context user
 * that POST /auth/refresh already loaded, so a sixth call would buy nothing and
 * cost the exact bug we know about.
 *
 * THE THREE-WAY STATE IS THE POINT, and it is why "reminders on/off" is not one
 * boolean. Consent (email_prefs.reminders_enabled, an email_suppressions row)
 * and schedule (reminder_local_time) are orthogonal per D-137(6), so a user can
 * be consented with no time set. That is a real state -- "on, but you have not
 * said when" -- and collapsing it into "off" would make the screen lie about
 * what an unsubscribe did.
 *
 * Design notes (anti-slop pre-flight). Brief: let a signed-in developer say
 * WHEN a reminder arrives and WHETHER each of the two emails is wanted. This is
 * a seventh instance of the ONE panel primitive the other Profile sections use,
 * not a new section type; the signature layout primitive is that panel and it is
 * simply repeated. Every value comes from the existing semantic tokens: no new
 * color, radius, shadow or font, no colored card edge, no gradient, no icon, no
 * emoji, no all-caps label, no numbered sequence, no stat row.
 *
 * Defaults deliberately NOT used: no custom animated toggle switch (this
 * codebase has no Switch primitive, and hand-rolling an iOS-style one would be
 * both novel and a slop-catalogue "component invented per screen" risk) -- the
 * controls are a native <input type="checkbox"> inside a bordered label row,
 * which is the same shape the app's existing bordered radio rows use and which
 * gets keyboard and screen-reader behaviour for free. Time uses a native
 * <input type="time"> rather than a bespoke picker, so mobile gets the platform
 * wheel and desktop gets typing. No success toast: the codebase expresses
 * success by re-rendering into the new state, and there is no toast anywhere.
 */

type Busy = null | 'time' | 'reminder' | 'recap';

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <section className="flex flex-col rounded-soft border border-border bg-surface-raised p-6 gap-3">
      <p className="text-sm text-ink-muted shrink-0">Reminders and recap</p>
      {children}
    </section>
  );
}

/**
 * A bordered label row wrapping a native checkbox. Selection is shown with the
 * same border-action + bg-action-tint pair the app already uses for a chosen
 * option, so "on" looks the same here as everywhere else.
 *
 * py-3 rather than the py-2 used on inline buttons: this whole row is the tap
 * target, and 12px of vertical padding around a ~20px line box clears the 44px
 * touch floor docs/08 asks for on a phone.
 */
function ToggleRow({
  checked,
  disabled,
  onChange,
  label,
  hint,
}: {
  checked: boolean;
  disabled: boolean;
  onChange: (next: boolean) => void;
  label: string;
  hint: string;
}) {
  return (
    <label
      className={`flex cursor-pointer items-start gap-3 rounded-soft border px-4 py-3 transition-colors duration-fast ${
        checked ? 'border-action bg-action-tint' : 'border-border'
      } ${disabled ? 'cursor-not-allowed opacity-50' : ''}`}
    >
      <input
        type="checkbox"
        className="mt-1 shrink-0 accent-action"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="min-w-0">
        <span className="block text-sm text-ink">{label}</span>
        <span className="block text-xs text-ink-muted">{hint}</span>
      </span>
    </label>
  );
}

export default function ReminderSection() {
  const { user, setUser } = useAuth();
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const [draftTime, setDraftTime] = useState('');

  if (!user) return null;

  const verified = user.email_verified && user.email !== null;
  // Render-safety fallback, NOT a contract assumption. The type says these are
  // always present and the server allowlist always sends them, but this card
  // renders inside Profile with no per-section boundary: reading through an
  // undefined `email_prefs` would white-screen the whole page, including the
  // five panels that have nothing to do with email. A user on a stale bundle
  // during a deploy is the realistic way that happens. Defaulting to "on"
  // matches the server, where the absence of a suppression row means allowed.
  const prefs: EmailPrefs = user.email_prefs ?? {
    reminders_enabled: true,
    recap_enabled: true,
  };
  const time = user.reminder_local_time ?? null;

  const run = async (which: Busy, action: () => Promise<void>) => {
    setBusy(which);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Something went wrong. Try again.',
      );
    } finally {
      setBusy(null);
    }
  };

  const saveTime = (next: string | null) =>
    run('time', async () => {
      const { user: updated } = await patchMe({ reminder_local_time: next });
      setUser(updated);
      setDraftTime('');
    });

  const savePrefs = (which: 'reminder' | 'recap', body: Partial<EmailPrefs>) =>
    run(which, async () => {
      const next = await patchEmailPrefs(body);
      setUser({ ...user, email_prefs: next });
    });

  // No verified address: reminders are not a thing that can be turned on yet.
  // The card still renders rather than hiding, because a missing card reads as
  // "this feature does not exist" and the user has no way to discover that
  // confirming an address is what unlocks it.
  if (!verified) {
    return (
      <Panel>
        <p className="text-sm text-ink">
          Add and confirm an email address above to turn on a daily reminder and the
          weekly recap.
        </p>
        <p className="text-xs text-ink-muted">
          Nothing is sent to an unconfirmed address.
        </p>
      </Panel>
    );
  }

  return (
    <Panel>
      <ToggleRow
        checked={prefs.reminders_enabled}
        disabled={busy !== null}
        onChange={(next) => savePrefs('reminder', { reminders_enabled: next })}
        label="Daily reminder"
        hint={
          prefs.reminders_enabled && time === null
            ? 'On, but no time set yet. Pick one below.'
            : 'One email a day, only if you have not read anything yet.'
        }
      />

      {prefs.reminders_enabled ? (
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm text-ink" htmlFor="reminder-time">
            Send at
          </label>
          <input
            id="reminder-time"
            type="time"
            // Uncontrolled-until-touched: `draftTime` is empty until the user
            // edits, so the field always shows the saved value on first paint
            // and never fights an update that arrived from elsewhere.
            value={draftTime || (time ?? '')}
            disabled={busy !== null}
            onChange={(event) => setDraftTime(event.target.value)}
            className="min-w-0 rounded-soft border border-border bg-surface-reading px-3 py-3 font-code text-sm text-ink focus:border-action focus:outline-none disabled:opacity-50"
          />
          <span className="text-xs text-ink-muted">
            {user.timezone} time
          </span>
          {draftTime && draftTime !== time ? (
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => saveTime(draftTime)}
              className="rounded-soft border border-border px-4 py-2 text-sm font-medium text-ink transition-colors duration-fast hover:border-action hover:text-action disabled:opacity-50 disabled:hover:border-border disabled:hover:text-ink"
            >
              {busy === 'time' ? 'Saving…' : 'Save time'}
            </button>
          ) : null}
          {time !== null && !draftTime ? (
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => saveTime(null)}
              // py-3 rather than the bare text-link styling used for inline
              // prose actions elsewhere: this is a real tap target sitting next
              // to a time input on a phone, and the narrow spec asserts it
              // clears the 44px floor.
              className="rounded-soft px-2 py-3 text-sm text-ink-muted underline hover:text-ink disabled:opacity-50"
            >
              Clear
            </button>
          ) : null}
        </div>
      ) : null}

      <ToggleRow
        checked={prefs.recap_enabled}
        disabled={busy !== null}
        onChange={(next) => savePrefs('recap', { recap_enabled: next })}
        label="Weekly recap"
        hint="Monday morning, covering the week just finished. Skipped if the week was empty."
      />

      {error ? (
        <p role="alert" className="text-sm text-ink">
          {error}
        </p>
      ) : null}
    </Panel>
  );
}
