import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError, patchMe } from '../lib/api';
import { useAuth } from '../lib/auth-context';
import type { Level } from '../lib/types';

const LEVELS: { id: Level; label: string; description: string }[] = [
  { id: 'junior', label: 'Junior', description: 'A few years in. Still building instincts for what looks wrong.' },
  { id: 'mid', label: 'Mid', description: 'Comfortable shipping. Reviewing others’ code is routine.' },
  { id: 'senior', label: 'Senior', description: 'You catch the subtle stuff. Sessions should aim high.' },
];

export function Onboarding() {
  const [level, setLevel] = useState<Level | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { setUser } = useAuth();
  const navigate = useNavigate();

  const submit = async () => {
    if (!level) return;
    setSaving(true);
    setError(null);
    try {
      const { user } = await patchMe({ level });
      setUser(user);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save that. Try again.');
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-8 px-6 py-12">
      <div>
        <h1 className="font-explanation text-3xl text-ink">Where are you starting from?</h1>
        <p className="mt-2 text-base text-ink-muted">This sets how hard the boss exercise in each session runs.</p>
      </div>
      <div className="flex flex-col gap-3">
        {LEVELS.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => setLevel(option.id)}
            aria-pressed={level === option.id}
            className={`rounded-loose border px-5 py-4 text-left transition-colors duration-fast ${
              level === option.id ? 'border-action bg-action-tint' : 'border-border'
            }`}
          >
            <p className="font-ui text-base font-medium text-ink">{option.label}</p>
            <p className="mt-1 text-sm text-ink-muted">{option.description}</p>
          </button>
        ))}
      </div>
      {error ? <p className="text-sm text-incorrect">{error}</p> : null}
      <button
        type="button"
        onClick={submit}
        disabled={!level || saving}
        // Disabled must READ as disabled. `opacity-40` on a filled primary kept
        // the "solid block = actionable" signal while pushing the label under
        // WCAG AA (docs/08), so it looked clickable and merely dim. Disabled
        // now drops the fill entirely and becomes a quiet outline: different in
        // KIND, not just in brightness, and the muted label keeps AA contrast.
        // The transparent border on the enabled state keeps the box stable, so
        // nothing shifts when it flips.
        className="self-start rounded-soft border border-transparent bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast disabled:cursor-not-allowed disabled:border-border disabled:bg-transparent disabled:text-ink-muted"
      >
        {saving ? 'Saving…' : 'Start today’s session'}
      </button>
    </div>
  );
}
