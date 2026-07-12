import { expect, test } from '@playwright/test';

// FIX-A: the dashboard's `Promise.all` used to reject the whole page load on
// any single failed fetch, blanking the first screen every user sees. Each
// panel now loads independently. This stubs the concepts endpoint to 500 while
// the session endpoint succeeds, and asserts the page still renders, the
// primary "enter session" CTA is present and navigates, and only the failed
// panel degrades to a "couldn't load" note. Hermetic: /auth/refresh is stubbed
// (onboarded user), so no seed/token-rotation is involved.

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

test('a failed dashboard panel degrades alone; page and primary CTA still render', async ({ page }) => {
  await page.route('**/v1/auth/refresh', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'stub', expires_in: 900, user: stubUser() }),
    });
  });

  // Primary panel data loads fine...
  await page.route('**/v1/session/today', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_date: '2026-07-12',
        completed: false,
        exercises: [{ attempted: false, concepts: ['off-by-one'] }],
      }),
    }),
  );
  // ...a secondary panel hard-fails...
  await page.route('**/v1/me/concepts', (route) =>
    route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: { code: 'internal', message: 'boom', request_id: 'req_x' } }),
    }),
  );
  // ...and the other secondary panel is fine.
  await page.route('**/v1/me/sessions**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  );

  await page.goto('/');

  // The page rendered (not a blank/error page): the greeting header is present.
  await expect(page.getByRole('heading', { name: 'tester' })).toBeVisible({ timeout: 15_000 });

  // The primary CTA is present AND clickable -- it navigates into the session.
  const cta = page.getByRole('link', { name: 'Enter sandbox' });
  await expect(cta).toBeVisible();

  // Only the failed panel degraded, with a readable note (not a blank page).
  await expect(page.getByText(/load upcoming reviews/i)).toBeVisible();

  await cta.click();
  await expect(page).toHaveURL(/\/session$/, { timeout: 15_000 });
});
