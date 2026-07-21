import { expect, test } from '@playwright/test';

// The session-complete screen (D-143). Hermetic, in the style of
// dashboard-resilience.spec.ts / streak-welcome-back.spec.ts: /auth/refresh is
// stubbed with an onboarded user, so no seed or token rotation is involved.
//
// Covers: the server-state guard in BOTH directions (D-143(2)), the three
// streak states (repair affordance / plain streak / none), the back path, and
// the narrow layout.

function stubUser() {
  return {
    id: 'u_test',
    username: 'tester',
    display_name: null,
    avatar_url: null,
    level: 'mid',
    timezone: 'UTC',
    onboarded: true,
  };
}

function stats(overrides: Record<string, unknown> = {}) {
  return {
    current_streak: 5,
    longest_streak: 14,
    streak_freezes: 1,
    total_attempts: 40,
    total_correct: 31,
    accuracy_by_type: {},
    last_active_local_date: '2026-07-21',
    total_sessions: 12,
    repair_available: false,
    repair_restores_to: null,
    ...overrides,
  };
}

async function stub(
  page: import('@playwright/test').Page,
  opts: { completed: boolean; stats?: Record<string, unknown>; tomorrow?: unknown },
) {
  await page.route('**/v1/auth/refresh', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'stub', expires_in: 900, user: stubUser() }),
    });
  });
  await page.route('**/v1/session/today', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_date: '2026-07-21',
        completed: opts.completed,
        tomorrow: opts.tomorrow ?? null,
        exercises: [{ attempted: opts.completed, concepts: ['off-by-one'] }],
      }),
    }),
  );
  await page.route('**/v1/me/stats', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(opts.stats ?? stats()) }),
  );
  // Dashboard-only panels, stubbed so a guard redirect to "/" renders cleanly.
  await page.route('**/v1/me/concepts', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  );
  await page.route('**/v1/me/sessions**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  );
}

test('a completed session renders the screen with a plain streak line and a way back', async ({ page }) => {
  await stub(page, { completed: true });
  await page.goto('/session/complete');

  await expect(page.getByRole('heading', { name: 'Session complete' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('5-day streak', { exact: false })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Back to dashboard' })).toBeVisible();
});

test('GUARD: reaching /session/complete without a completed session redirects to the dashboard', async ({
  page,
}) => {
  // The negative on the guard (D-143(2)): completion is server state, not
  // navigation history, so a deep-link to an unfinished day must not show it.
  await stub(page, { completed: false });
  await page.goto('/session/complete');

  // Landed on the dashboard (its greeting header), and NONE of the completion
  // copy is present.
  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });
  await expect(page).toHaveURL('/');
  await expect(page.getByRole('heading', { name: 'Session complete' })).toHaveCount(0);
});

test('a repairable reset shows the A1 welcome-back affordance on the complete screen', async ({ page }) => {
  await stub(page, { completed: true, stats: stats({ repair_available: true, repair_restores_to: 16 }) });
  let repairCalls = 0;
  await page.route('**/v1/streak/repair', async (route) => {
    repairCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ current_streak: 16, repaired: true }),
    });
  });

  await page.goto('/session/complete');
  await expect(page.getByRole('heading', { name: 'Session complete' })).toBeVisible({ timeout: 15_000 });
  // The A1 "celebrate the return" state, now built on session-complete too.
  await expect(page.getByText('Good to see you again.')).toBeVisible();
  const restore = page.getByRole('button', { name: 'Restore your 16-day streak' });
  await expect(restore).toBeVisible();

  await restore.click();
  await expect(page.getByText(/Your streak is back at/i)).toBeVisible();
  await expect(restore).toHaveCount(0);
  expect(repairCalls).toBe(1);
});

test('the complete screen is usable at the narrow width', async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 800 });
  await stub(page, {
    completed: true,
    tomorrow: { concept: 'dict-mutation-during-iteration', first_completed_session: false, is_fallback: false },
  });
  await page.goto('/session/complete');

  await expect(page.getByRole('heading', { name: 'Session complete' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('link', { name: 'Back to dashboard' })).toBeVisible();
  await expect(page.getByText('Coming up for review tomorrow: dict mutation during iteration.')).toBeVisible();
});
