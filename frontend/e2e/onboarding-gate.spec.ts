import { expect, test } from '@playwright/test';

// H2: onboarding is a hard gate, not just the "/" landing. A non-onboarded
// user deep-linking straight to /session used to reach the session player with
// no level set (RequireAuth checked only auth status, never user.onboarded).
// These tests stub POST /v1/auth/refresh to control the `onboarded` flag
// directly -- hermetic, so no seeded user and no refresh-token rotation are in
// play (the token rotates on first use; stubbing sidesteps that entirely).

function stubUser(onboarded: boolean) {
  return {
    id: 'u_test',
    username: 'tester',
    display_name: null,
    avatar_url: null,
    level: 'mid',
    timezone: 'UTC',
    onboarded,
  };
}

async function stubRefresh(page: import('@playwright/test').Page, onboarded: boolean) {
  await page.route('**/v1/auth/refresh', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'stub-token', expires_in: 900, user: stubUser(onboarded) }),
    });
  });
}

test('non-onboarded user deep-linking to /session is redirected to /onboarding', async ({ page }) => {
  await stubRefresh(page, false);

  await page.goto('/session');

  await expect(page).toHaveURL(/\/onboarding$/, { timeout: 15_000 });
  await expect(
    page.getByRole('heading', { name: /Where are you starting from/i }),
  ).toBeVisible();
});

test('already-onboarded user visiting /onboarding is redirected to the dashboard', async ({ page }) => {
  await stubRefresh(page, true);

  // The redirect happens before the dashboard fetches, so a "/" URL is enough
  // proof; the dashboard's own data loading is not under test here.
  await page.goto('/onboarding');

  await expect(page).toHaveURL(/localhost:5173\/$/, { timeout: 15_000 });
});
