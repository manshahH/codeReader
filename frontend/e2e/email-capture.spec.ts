import { expect, test } from '@playwright/test';

/**
 * A2 email capture (docs/10; D-120): capture, confirm, and the invalid-token
 * path.
 *
 * Hermetic. /auth/refresh and the /v1/me/email routes are stubbed, so these run
 * without the local stack, without a database, and without sending mail. That
 * is the right call here: what is under test is the CLIENT state machine (four
 * states, what each one shows, and that the confirmed address is never dropped
 * while another is pending). The server's rules have their own 49 tests in
 * backend/tests/test_a2_email_capture.py, and duplicating them through a
 * browser would be slower and prove less.
 *
 * The Profile's other five panels are stubbed to empty/500 as convenient: they
 * degrade independently (usePanel), and the email card deliberately makes no
 * fetch of its own, so none of them can affect it.
 */

type EmailState = {
  email: string | null;
  email_verified: boolean;
  pending_email: string | null;
};

function stubUser(overrides: Partial<EmailState> = {}) {
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
    // A3 (D-137): the Profile now renders a reminders card from these two.
    // Omitting them would exercise the component's render-safety fallback
    // instead of the real shape, which is not what these specs are testing.
    reminder_local_time: null,
    email_prefs: { reminders_enabled: true, recap_enabled: true },
    ...overrides,
  };
}

async function stubApp(page: import('@playwright/test').Page, user: object) {
  await page.route('**/v1/auth/refresh', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'stub', expires_in: 900, user }),
    });
  });

  // The five panels the Profile does fetch. Empty is fine; the email card is
  // independent of all of them.
  await page.route('**/v1/me/stats', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        current_streak: 0,
        longest_streak: 0,
        streak_freezes: 0,
        total_attempts: 0,
        total_correct: 0,
        accuracy_by_type: {},
        last_active_local_date: null,
        total_sessions: 0,
        repair_available: false,
        repair_restores_to: null,
      }),
    }),
  );
  for (const path of [
    '**/v1/me/concepts',
    '**/v1/me/activity**',
    '**/v1/me/accuracy-history**',
    '**/v1/me/sessions**',
  ]) {
    await page.route(path, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
    );
  }
  await page.route('**/v1/me/review', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ reviewed: false, review: null }),
    }),
  );
}

function json(body: unknown, status = 200) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

test('capture: submitting an address moves the card to the pending state', async ({ page }) => {
  await stubApp(page, stubUser());

  let captured: string | null = null;
  await page.route('**/v1/me/email', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    captured = (route.request().postDataJSON() as { email: string }).email;
    await route.fulfill(
      json({ email: null, email_verified: false, pending_email: captured }),
    );
  });

  await page.goto('/profile');

  await expect(page.getByText(/No address on file/i)).toBeVisible({ timeout: 15_000 });

  await page.getByLabel('Email address').fill('dev@example.com');
  await page.getByRole('button', { name: 'Send confirmation link' }).click();

  await expect(page.getByText(/Waiting on/i)).toBeVisible();
  await expect(page.getByText('dev@example.com')).toBeVisible();
  expect(captured).toBe('dev@example.com');

  // The UI throttle mirrors the server's: the resend affordance is offered but
  // disabled with a countdown, rather than inviting a click that would 429.
  const resend = page.getByRole('button', { name: /Resend in \d+s/ });
  await expect(resend).toBeVisible();
  await expect(resend).toBeDisabled();
});

test('capture: a pending address never displaces the confirmed one', async ({ page }) => {
  // The D-120(2) rule, seen from the UI: the user must be able to tell that
  // their working address is still working while a new one is unconfirmed.
  await stubApp(page, stubUser({ email: 'old@example.com', email_verified: true }));

  await page.route('**/v1/me/email', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill(
      json({ email: 'old@example.com', email_verified: true, pending_email: 'new@example.com' }),
    );
  });

  await page.goto('/profile');

  await expect(page.getByText('old@example.com')).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: 'Change' }).click();
  await page.getByLabel('New address').fill('new@example.com');
  await page.getByRole('button', { name: 'Send confirmation link' }).click();

  await expect(page.getByText(/Waiting on/i)).toBeVisible();
  await expect(page.getByText('new@example.com')).toBeVisible();
  // The load-bearing assertion: the old address is still shown as the live one.
  // It appears TWICE by design -- once as the confirmed address at the top of
  // the card, once inside the "reminders keep going to ___" sentence -- so this
  // scopes to the sentence rather than matching the bare string.
  await expect(page.getByText(/reminders keep going to old@example\.com/i)).toBeVisible();
  await expect(page.getByText('old@example.com')).toHaveCount(2);
});

test('verify: a good token confirms the address and reports it', async ({ page }) => {
  await stubApp(page, stubUser({ pending_email: 'dev@example.com' }));

  let sentToken: string | null = null;
  await page.route('**/v1/me/email/verify', async (route) => {
    sentToken = (route.request().postDataJSON() as { token: string }).token;
    await route.fulfill(
      json({ email: 'dev@example.com', email_verified: true, pending_email: null }),
    );
  });

  await page.goto('/verify-email?token=a-good-token');

  await expect(page.getByText(/Confirmed/i)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('dev@example.com')).toBeVisible();
  expect(sentToken).toBe('a-good-token');

  await page.getByRole('link', { name: 'Go to profile' }).click();
  await expect(page).toHaveURL(/\/profile$/);
});

test('verify: an invalid token shows the generic failure and a way forward', async ({ page }) => {
  await stubApp(page, stubUser());

  await page.route('**/v1/me/email/verify', (route) =>
    route.fulfill(
      json(
        {
          error: {
            code: 'verification_failed',
            message: 'That verification link is not valid or has expired.',
            request_id: 'req_x',
          },
        },
        400,
      ),
    ),
  );

  await page.goto('/verify-email?token=expired-or-forged');

  await expect(page.getByRole('alert')).toContainText(/not valid or has expired/i);
  // Never confirms anything about the token: no "already used", no "not yours".
  await expect(page.getByText(/already used|belongs to|another account/i)).toHaveCount(0);
  // The user is told what to do next rather than left on a dead end.
  await expect(page.getByText(/Send a fresh one from your profile/i)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Go to profile' })).toBeVisible();
});

test('verify: a link with no token fails without calling the API', async ({ page }) => {
  await stubApp(page, stubUser());

  let called = false;
  await page.route('**/v1/me/email/verify', (route) => {
    called = true;
    return route.fulfill(json({ email: null, email_verified: false, pending_email: null }));
  });

  await page.goto('/verify-email');

  await expect(page.getByRole('alert')).toContainText(/missing its confirmation code/i);
  expect(called).toBe(false);
});
