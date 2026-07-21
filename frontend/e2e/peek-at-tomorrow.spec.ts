import { expect, test } from '@playwright/test';

// A4 "peek at tomorrow" (D-142), shown on the DASHBOARD completed state
// (D-144: dashboard-only, reversing the brief D-143 screen placement). Driven
// by SessionResponse.tomorrow, which is now purely {concept, is_fallback} --
// the first-day warmth moved to the session-complete screen. These stub the
// dashboard hermetically (onboarded user via a stubbed /auth/refresh) and
// assert:
//  - completed + scheduled concept -> the forward hook renders with a date;
//  - completed + fallback           -> "Next up" with NO date claim;
//  - completed + tomorrow null      -> nothing renders (the empty case);
//  - the hook is present at the narrow width too.

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

type TomorrowStub = { concept: string; is_fallback: boolean } | null;

async function stubDashboard(page: import('@playwright/test').Page, tomorrow: TomorrowStub) {
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
        completed: true,
        first_completed_session: false,
        tomorrow,
        exercises: [{ attempted: true, concepts: ['off-by-one'] }],
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
      body: JSON.stringify({ repair_available: false, repair_restores_to: null }),
    }),
  );
}

test('the dashboard completed state shows the tomorrow hook (scheduled)', async ({ page }) => {
  await stubDashboard(page, { concept: 'dict-mutation-during-iteration', is_fallback: false });
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('link', { name: /review today/i })).toBeVisible();
  await expect(page.getByText('Coming up for review tomorrow: dict mutation during iteration.')).toBeVisible();
});

test('the fallback hook says "Next up" with no date claim', async ({ page }) => {
  await stubDashboard(page, { concept: 'dict-mutation-during-iteration', is_fallback: true });
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('Next up: dict mutation during iteration.')).toBeVisible();
  // The fallback must NOT assert a date -- the concept is not scheduled tomorrow.
  await expect(page.getByText(/coming up for review tomorrow/i)).toHaveCount(0);
});

test('the dashboard with nothing due tomorrow shows no hook (empty case)', async ({ page }) => {
  await stubDashboard(page, null);
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('link', { name: /review today/i })).toBeVisible();
  await expect(page.getByText(/coming up for review tomorrow/i)).toHaveCount(0);
  await expect(page.getByText(/next up:/i)).toHaveCount(0);
});

test('the tomorrow hook renders at the narrow width', async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 800 });
  await stubDashboard(page, { concept: 'dict-mutation-during-iteration', is_fallback: false });
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('Coming up for review tomorrow: dict mutation during iteration.')).toBeVisible();
});
