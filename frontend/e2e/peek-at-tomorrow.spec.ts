import { expect, test } from '@playwright/test';

// A4 "peek at tomorrow" (D-142), now shown on the SESSION-COMPLETE screen
// (D-143(3)): the teaser moved off the dashboard and onto the finish moment.
// Driven by SessionResponse.tomorrow. These stub the screen hermetically
// (onboarded user via a stubbed /auth/refresh, no seed/token rotation) and
// assert:
//  - completed + tomorrow present -> the hook renders (plain, warm, fallback);
//  - completed + tomorrow null     -> nothing renders (the empty case);
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

async function stubComplete(page: import('@playwright/test').Page, tomorrow: TomorrowStub) {
  await page.route('**/v1/auth/refresh', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'stub', expires_in: 900, user: stubUser() }),
    });
  });
  // A COMPLETED session, carrying the teaser under test -- the screen's guard
  // reads `completed` from here.
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
  // repair_restores_to null -> the A1 welcome-back panel stays hidden; a plain
  // streak line shows instead. Not relevant to the teaser assertions.
  await page.route('**/v1/me/stats', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ current_streak: 3, repair_available: false, repair_restores_to: null }),
    }),
  );
}

test('the complete screen shows the tomorrow hook (plain variant)', async ({ page }) => {
  await stubComplete(page, { concept: 'dict-mutation-during-iteration', first_completed_session: false });
  await page.goto('/session/complete');

  await expect(page.getByRole('heading', { name: 'Session complete' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('Coming up for review tomorrow: dict mutation during iteration.')).toBeVisible();
});

test('first-ever completed day shows the warm one-time lead-in (scheduled)', async ({ page }) => {
  await stubComplete(page, {
    concept: 'dict-mutation-during-iteration',
    first_completed_session: true,
    is_fallback: false,
  });
  await page.goto('/session/complete');

  await expect(page.getByRole('heading', { name: 'Session complete' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/That’s your first day done\./)).toBeVisible();
  await expect(page.getByText(/is coming up for review tomorrow/)).toBeVisible();
});

test('first-completed fallback shows "Next up" with no date claim', async ({ page }) => {
  await stubComplete(page, {
    concept: 'dict-mutation-during-iteration',
    first_completed_session: true,
    is_fallback: true,
  });
  await page.goto('/session/complete');

  await expect(page.getByRole('heading', { name: 'Session complete' })).toBeVisible({ timeout: 15_000 });
  await expect(
    page.getByText('That’s your first day done. Next up: dict mutation during iteration.'),
  ).toBeVisible();
  // The fallback must NOT assert a date -- it is not scheduled for tomorrow.
  await expect(page.getByText(/coming up for review tomorrow/i)).toHaveCount(0);
});

test('the complete screen with nothing due tomorrow shows no hook (empty case)', async ({ page }) => {
  await stubComplete(page, null);
  await page.goto('/session/complete');

  await expect(page.getByRole('heading', { name: 'Session complete' })).toBeVisible({ timeout: 15_000 });
  // No teaser copy anywhere.
  await expect(page.getByText(/coming up for review tomorrow/i)).toHaveCount(0);
  await expect(page.getByText(/next up:/i)).toHaveCount(0);
});

test('the tomorrow hook renders at the narrow width', async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 800 });
  await stubComplete(page, { concept: 'dict-mutation-during-iteration', first_completed_session: false });
  await page.goto('/session/complete');

  await expect(page.getByRole('heading', { name: 'Session complete' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('Coming up for review tomorrow: dict mutation during iteration.')).toBeVisible();
});
