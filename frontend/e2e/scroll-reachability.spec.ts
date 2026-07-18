import { expect, test } from '@playwright/test';

/**
 * D-125: content below the fold must be reachable on every full-height screen.
 *
 * Found by using the app, not by a test. AppLayout's <main> is
 * `overflow-hidden`, so each screen owns its own scroll container. Profile.tsx
 * has always had `overflow-y-auto`; Dashboard.tsx did not, and once A1 added
 * the welcome-back panel the page grew past the fold and "Upcoming reviews" /
 * "Recent sessions" became unreachable.
 *
 * This class of bug is invisible to every other test we have. Playwright's
 * locators resolve and even click elements that are clipped out of view, and
 * jsdom-style assertions never lay anything out at all, so a screen can be
 * completely unusable while every selector-based test stays green. The
 * assertion has to be about SCROLLABILITY, not about presence.
 *
 * Hermetic: stubs are sized to force overflow deterministically rather than
 * depending on how much real content the local DB happens to hold.
 */

function stubUser() {
  return {
    id: 'u_test',
    username: 'tester',
    display_name: null,
    avatar_url: null,
    level: 'mid',
    timezone: 'UTC',
    onboarded: true,
    email: null,
    email_verified: false,
    pending_email: null,
  };
}

async function stubDashboard(page: import('@playwright/test').Page) {
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
  // Plenty of rows, so the page is guaranteed taller than the viewport.
  await page.route('**/v1/me/concepts', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        Array.from({ length: 25 }, (_, i) => ({
          concept: `concept-number-${i}`,
          mastery: 0.4,
          attempts: 3,
          next_review_at: '2026-07-20T00:00:00Z',
        })),
      ),
    }),
  );
  await page.route('**/v1/me/sessions**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        Array.from({ length: 25 }, (_, i) => ({
          session_date: `2026-06-${String((i % 28) + 1).padStart(2, '0')}`,
          completed: true,
          correct_count: 3,
          exercise_count: 5,
          skipped_count: 0,
          concepts: ['off-by-one'],
        })),
      ),
    }),
  );
  await page.route('**/v1/me/stats', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        current_streak: 3,
        longest_streak: 9,
        streak_freezes: 2,
        total_attempts: 40,
        total_correct: 25,
        accuracy_by_type: { spot_the_bug: 0.7 },
        last_active_local_date: '2026-07-18',
        total_sessions: 12,
        // The welcome-back panel is what pushed this screen past the fold in
        // the first place, so the regression test renders it.
        repair_available: true,
        repair_restores_to: 9,
      }),
    }),
  );
  await page.route('**/v1/me/review', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ reviewed: false, review: null }),
    }),
  );
  await page.route('**/v1/me/activity**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  );
  await page.route('**/v1/me/accuracy-history**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  );
}

/** The one screen-level element that is allowed to scroll, per AppLayout. */
async function scrollState(page: import('@playwright/test').Page, selector: string) {
  return page.locator(selector).evaluate((el) => ({
    scrollHeight: el.scrollHeight,
    clientHeight: el.clientHeight,
    canScroll: el.scrollHeight > el.clientHeight,
    overflowY: getComputedStyle(el).overflowY,
  }));
}

test('dashboard: content below the fold is reachable', async ({ page }) => {
  await stubDashboard(page);
  // A laptop-height viewport, which is where this was actually hit. The
  // dashboard's inner panels scroll internally, so the page only overflows once
  // the header, the welcome-back panel and the CTA stack above them.
  await page.setViewportSize({ width: 1280, height: 600 });
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });

  const root = 'main > div';
  const state = await scrollState(page, root);

  // The page really is taller than the viewport, so this test is meaningful.
  expect(state.scrollHeight, 'stub content should overflow the viewport').toBeGreaterThan(
    state.clientHeight,
  );
  // ...and the container is allowed to scroll rather than clipping.
  expect(['auto', 'scroll']).toContain(state.overflowY);

  // The decisive check: scrolling actually moves. A clipped container reports
  // scrollTop 0 forever no matter what you ask it to do.
  const moved = await page.locator(root).evaluate((el) => {
    el.scrollTop = el.scrollHeight;
    return el.scrollTop;
  });
  expect(moved, 'the dashboard must scroll, not clip').toBeGreaterThan(0);
});

test('profile: content below the fold is reachable', async ({ page }) => {
  // The screen that was already correct, kept as the control so a future
  // layout change cannot quietly break both at once.
  await stubDashboard(page);
  await page.setViewportSize({ width: 1280, height: 700 });
  await page.goto('/profile');

  await expect(page.getByText('Signed in as')).toBeVisible({ timeout: 15_000 });

  const state = await scrollState(page, 'main > div');
  expect(['auto', 'scroll']).toContain(state.overflowY);

  const moved = await page.locator('main > div').evaluate((el) => {
    el.scrollTop = el.scrollHeight;
    return el.scrollTop;
  });
  expect(moved, 'the profile must scroll, not clip').toBeGreaterThan(0);
});
