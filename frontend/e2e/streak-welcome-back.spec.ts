import { expect, test } from '@playwright/test';

// A1 streak safety net (docs/10; D-116). Covers the "celebrate the return"
// state on the Dashboard: the welcome-back panel appears only when a repair is
// actually available, the restore affordance calls POST /v1/streak/repair with
// an Idempotency-Key, the panel reports the restored value, and the offer is
// gone once used. Also covers the negative: no offer, no panel.
//
// Hermetic, in the style of dashboard-resilience.spec.ts: /auth/refresh is
// stubbed with an onboarded user, so no seed or token rotation is involved.

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

function baseStats(overrides: Record<string, unknown> = {}) {
  return {
    current_streak: 2,
    longest_streak: 14,
    streak_freezes: 1,
    total_attempts: 40,
    total_correct: 31,
    accuracy_by_type: {},
    last_active_local_date: '2026-07-18',
    total_sessions: 12,
    repair_available: false,
    repair_restores_to: null,
    ...overrides,
  };
}

async function stubDashboard(page, stats: Record<string, unknown>) {
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
        session_date: '2026-07-18',
        completed: false,
        exercises: [{ attempted: false, concepts: ['off-by-one'] }],
      }),
    }),
  );
  await page.route('**/v1/me/concepts', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  );
  await page.route('**/v1/me/sessions**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  );
  await page.route('**/v1/me/stats', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(stats),
    }),
  );
}

test('a repairable reset shows the welcome-back state and restores the streak', async ({ page }) => {
  await stubDashboard(page, baseStats({ repair_available: true, repair_restores_to: 16 }));

  let repairCalls = 0;
  let sawIdempotencyKey = false;
  await page.route('**/v1/streak/repair', async (route) => {
    repairCalls += 1;
    sawIdempotencyKey = Boolean(route.request().headers()['idempotency-key']);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ current_streak: 16, repaired: true }),
    });
  });

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });

  // Warm, non-guilt copy, and the affordance names the value it restores.
  await expect(page.getByText('Good to see you again.')).toBeVisible();
  const restore = page.getByRole('button', { name: 'Restore your 16-day streak' });
  await expect(restore).toBeVisible();

  // The primary CTA still outranks it: today's session is not displaced.
  await expect(page.getByRole('link', { name: 'Enter sandbox' })).toBeVisible();

  await restore.click();

  await expect(page.getByText(/Your streak is back at/i)).toBeVisible();
  await expect(page.getByText('16')).toBeVisible();
  // The offer is single-use in the UI: the button is gone once taken.
  await expect(restore).toHaveCount(0);
  expect(repairCalls).toBe(1);
  expect(sawIdempotencyKey).toBe(true);
});

test('no repair available means no welcome-back panel at all', async ({ page }) => {
  await stubDashboard(page, baseStats());

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });

  // Negative: the affordance must not appear for users with nothing to restore.
  await expect(page.getByText('Good to see you again.')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Restore your/ })).toHaveCount(0);
});

test('a failed repair retires the offer quietly instead of showing an error', async ({ page }) => {
  await stubDashboard(page, baseStats({ repair_available: true, repair_restores_to: 9 }));
  // 409: the window closed or another tab already used it. Nothing was lost and
  // there is nothing for the reader to fix, so the panel must not scold.
  await page.route('**/v1/streak/repair', (route) =>
    route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({
        error: { code: 'not_repairable', message: 'nope', request_id: 'req_x' },
      }),
    }),
  );

  await page.goto('/');
  const restore = page.getByRole('button', { name: 'Restore your 9-day streak' });
  await expect(restore).toBeVisible({ timeout: 15_000 });
  await restore.click();

  await expect(restore).toHaveCount(0);
  await expect(page.getByText(/error|failed|sorry/i)).toHaveCount(0);
  // The rest of the dashboard is untouched.
  await expect(page.getByRole('link', { name: 'Enter sandbox' })).toBeVisible();
});
