import { expect, test } from '@playwright/test';

// Auth: no real GitHub OAuth here. scripts/seed_e2e.py issues a refresh
// token through the exact same app.auth.tokens code the real OAuth callback
// uses, and this test sets it as the `rt` cookie directly -- the SPA's
// normal POST /auth/refresh flow (RootGate) takes it from there. This is
// the "login (seed)" step from the milestone's success criteria, not a
// bypass of the auth code itself.
const API_BASE = process.env.E2E_API_BASE_URL ?? 'http://localhost:8000';
const REFRESH_TOKEN = process.env.E2E_REFRESH_TOKEN;

if (!REFRESH_TOKEN) {
  throw new Error(
    'E2E_REFRESH_TOKEN env var is required (run CODEREADER_ALLOW_SEED=1 python scripts/seed_e2e.py and export it)',
  );
}

test('full session: login (seed) -> one of each type -> reveal -> complete', async ({ page, context }) => {
  page.on('console', (msg) => console.log(`[browser:${msg.type()}] ${msg.text()}`));
  page.on('pageerror', (err) => console.log(`[pageerror] ${err.message}`));
  page.on('requestfailed', (req) => console.log(`[requestfailed] ${req.url()} ${req.failure()?.errorText}`));
  page.on('response', (res) => {
    if (res.url().includes('/v1/')) console.log(`[response] ${res.status()} ${res.url()}`);
  });

  const apiUrl = new URL(API_BASE);
  await context.addCookies([
    {
      name: 'rt',
      value: REFRESH_TOKEN as string,
      domain: apiUrl.hostname,
      path: '/',
      httpOnly: true,
      secure: false,
      sameSite: 'Lax',
    },
  ]);

  await page.goto('/');
  await expect(page).toHaveURL(/\/session$/, { timeout: 15_000 });

  for (let i = 0; i < 3; i++) {
    const typeLabel = page.locator('span.capitalize').first();
    await expect(typeLabel).toBeVisible({ timeout: 15_000 });
    const label = (await typeLabel.textContent())?.toLowerCase().trim() ?? '';

    if (label.includes('spot the bug')) {
      await page.getByRole('button', { name: 'Select line 1' }).click();
      await page.getByRole('radio', { name: 'Mutable default argument shared across calls' }).click();
    } else if (label.includes('trace')) {
      await page.getByRole('radio', { name: '2', exact: true }).click();
    } else if (label.includes('summarize')) {
      await page
        .getByLabel(/Describe what this does/i)
        .fill(
          'Retries the call with exponential backoff, only for connection or timeout errors, and re-raises the original exception after the final attempt.',
        );
    } else {
      throw new Error(`Unrecognized exercise type label: "${label}"`);
    }

    await page.getByRole('button', { name: 'Check answer' }).click();

    // summarize may land in the grading_pending -> polling path; deterministic
    // types grade synchronously. Either way, a verdict must eventually show.
    await expect(page.getByText(/^(Correct|Incorrect)\.$/)).toBeVisible({ timeout: 25_000 });

    await page.getByRole('button', { name: 'Next' }).click();
  }

  await expect(page.getByText('Session complete')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/correct today\.|done for today\./)).toBeVisible();
});
