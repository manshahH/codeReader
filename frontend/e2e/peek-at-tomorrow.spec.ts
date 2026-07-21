import { expect, test } from '@playwright/test';

// A4 "peek at tomorrow" (D-142). The teaser is a single-concept hook on the
// Dashboard's COMPLETED state, driven by SessionResponse.tomorrow. These stub
// the whole dashboard hermetically (onboarded user via a stubbed /auth/refresh,
// no seed/token rotation) and assert:
//  - completed + tomorrow present  -> the hook renders (plain and warm variants);
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

type TomorrowStub =
  | { concept: string; first_completed_session: boolean; is_fallback?: boolean }
  | null;

async function stubDashboard(page: import('@playwright/test').Page, tomorrow: TomorrowStub) {
  await page.route('**/v1/auth/refresh', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'stub', expires_in: 900, user: stubUser() }),
    });
  });
  // A COMPLETED single-exercise session, carrying the teaser under test.
  await page.route('**/v1/session/today', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_date: '2026-07-21',
        completed: true,
        tomorrow,
        exercises: [{ attempted: true, concepts: ['off-by-one'] }],
      }),
    }),
  );
  // Secondary panels: enough to render, none relevant to the teaser.
  await page.route('**/v1/me/concepts', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  );
  await page.route('**/v1/me/sessions**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  );
  // repair_restores_to null -> the A1 welcome-back panel stays hidden.
  await page.route('**/v1/me/stats', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ repair_available: false, repair_restores_to: null }),
    }),
  );
}

test('completed dashboard shows the tomorrow hook (plain variant)', async ({ page }) => {
  await stubDashboard(page, { concept: 'dict-mutation-during-iteration', first_completed_session: false });
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });
  // The completed state is up (review CTA), and the hook names exactly one concept.
  await expect(page.getByRole('link', { name: /review today/i })).toBeVisible();
  await expect(page.getByText('Coming up for review tomorrow: dict mutation during iteration.')).toBeVisible();
});

test('first-ever completed day shows the warm one-time lead-in (scheduled)', async ({ page }) => {
  await stubDashboard(page, {
    concept: 'dict-mutation-during-iteration',
    first_completed_session: true,
    is_fallback: false,
  });
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/That’s your first day done\./)).toBeVisible();
  await expect(page.getByText(/is coming up for review tomorrow/)).toBeVisible();
});

test('first-completed fallback shows "Next up" with no date claim', async ({ page }) => {
  await stubDashboard(page, {
    concept: 'dict-mutation-during-iteration',
    first_completed_session: true,
    is_fallback: true,
  });
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });
  await expect(
    page.getByText('That’s your first day done. Next up: dict mutation during iteration.'),
  ).toBeVisible();
  // The fallback must NOT assert a date -- it is not scheduled for tomorrow.
  await expect(page.getByText(/coming up for review tomorrow/i)).toHaveCount(0);
});

test('completed dashboard with nothing due tomorrow shows no hook (empty case)', async ({ page }) => {
  await stubDashboard(page, null);
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('link', { name: /review today/i })).toBeVisible();
  // No teaser copy anywhere.
  await expect(page.getByText(/coming up for review tomorrow/i)).toHaveCount(0);
});

test('the tomorrow hook renders at the narrow width', async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 800 });
  await stubDashboard(page, { concept: 'dict-mutation-during-iteration', first_completed_session: false });
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('Coming up for review tomorrow: dict mutation during iteration.')).toBeVisible();
});
