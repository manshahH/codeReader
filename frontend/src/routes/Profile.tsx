import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { GutterTick } from '../components/gutter/Gutter';
import { ApiError, getMeConcepts, getMeStats } from '../lib/api';
import { useAuth } from '../lib/auth-context';
import type { ConceptMastery, MeStats } from '../lib/types';

function StreakColumn({ current, longest }: { current: number; longest: number }) {
  const ticks = Array.from({ length: Math.max(current, 1) }, (_, i) => i < current);
  return (
    <div>
      <p className="text-sm text-ink-muted">Current streak</p>
      <p className="font-explanation text-3xl text-ink">{current} days</p>
      <div className="mt-3 flex flex-wrap gap-1" aria-label={`${current}-day streak`}>
        {ticks.map((filled, i) => (
          <GutterTick key={i} filled={filled} />
        ))}
      </div>
      <p className="mt-2 text-sm text-ink-muted">Longest: {longest} days</p>
    </div>
  );
}

export function Profile() {
  const [stats, setStats] = useState<MeStats | null>(null);
  const [concepts, setConcepts] = useState<ConceptMastery[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([getMeStats(), getMeConcepts()])
      .then(([statsBody, conceptsBody]) => {
        setStats(statsBody);
        setConcepts(conceptsBody);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load your profile.'));
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  if (error) return <p className="p-6 text-incorrect">{error}</p>;
  if (!stats || !concepts) return <p className="p-6 text-ink-muted">Loading…</p>;

  const accuracyEntries = Object.entries(stats.accuracy_by_type);
  const weakest = concepts.slice(0, 5);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-10 px-4 py-8">
      <div>
        <p className="text-sm text-ink-muted">Signed in as</p>
        <p className="font-ui text-lg text-ink">{user?.display_name ?? user?.username}</p>
      </div>

      <StreakColumn current={stats.current_streak} longest={stats.longest_streak} />

      <div>
        <p className="mb-3 text-sm text-ink-muted">Accuracy by type</p>
        <div className="flex flex-col gap-2">
          {accuracyEntries.length === 0 ? (
            <p className="text-sm text-ink-muted">No attempts yet.</p>
          ) : (
            accuracyEntries.map(([type, accuracy]) => (
              <div key={type} className="flex items-center justify-between border-b border-border py-2">
                <span className="font-code text-sm capitalize text-ink">{type.replace(/_/g, ' ')}</span>
                <span className="font-code text-sm text-ink-muted">{Math.round(accuracy * 100)}%</span>
              </div>
            ))
          )}
        </div>
      </div>

      <div>
        <p className="mb-3 text-sm text-ink-muted">Weakest concepts</p>
        <div className="flex flex-col gap-2">
          {weakest.length === 0 ? (
            <p className="text-sm text-ink-muted">Not enough data yet.</p>
          ) : (
            weakest.map((concept) => (
              <div key={concept.concept} className="flex items-center justify-between border-b border-border py-2">
                <span className="text-sm text-ink">{concept.concept.replace(/-/g, ' ')}</span>
                <span className="font-code text-sm text-ink-muted">{Math.round(concept.mastery * 100)}%</span>
              </div>
            ))
          )}
        </div>
      </div>

      <button type="button" onClick={handleLogout} className="self-start text-sm text-ink-muted underline hover:text-ink">
        Sign out
      </button>
    </div>
  );
}
