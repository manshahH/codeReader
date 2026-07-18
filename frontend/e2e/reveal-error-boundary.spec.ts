import { expect, test } from '@playwright/test';

import { localStackIsUp, seedAuthCookie, STACK_REQUIRED } from './_seed';

// C2 regression: a malformed grade `reveal` used to throw during render and,
// with no React error boundary anywhere, white-screen the whole SPA mid
// session. This drives a real session but intercepts POST /v1/attempts to
// return a graded response whose `reveal` is a non-object (1), which throws in
// Reveal's render. The session-level ErrorBoundary must turn that into a
// readable "skip this exercise" state, and skipping must let the session
// continue -- never a blank page.

test('malformed reveal renders an error state and the session continues', async ({ page, context }) => {
  test.skip(!(await localStackIsUp()), STACK_REQUIRED);

  page.on('pageerror', (err) => console.log(`[pageerror] ${err.message}`));

  await seedAuthCookie(context);

  // Force the grade result to carry a malformed reveal. `reveal: 1` is a
  // non-object, so `'explanation' in attempt.reveal` throws a TypeError during
  // Reveal's render -- the exact class of failure the boundary must contain.
  await page.route('**/v1/attempts', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        attempt_id: 999999,
        status: 'graded',
        is_correct: true,
        reveal: 1,
        percentile: null,
        streak: null,
        session: { completed: false, remaining: 1, first_completed_session: false },
      }),
    });
  });

  // Go straight to the session player (a direct /session deep-link is a
  // supported route; RequireAuth resolves the seed cookie into a session).
  // This deliberately sidesteps the dashboard's multi-call landing page --
  // this test is about the session-player error boundary, not the dashboard.
  await page.goto('/session');

  // Answer whatever the first exercise is (any valid answer -- the response is
  // intercepted regardless of correctness).
  const typeLabel = page.locator('span.capitalize').first();
  await expect(typeLabel).toBeVisible({ timeout: 15_000 });
  const label = (await typeLabel.textContent())?.toLowerCase().trim() ?? '';
  if (label.includes('spot the bug')) {
    await page.getByRole('button', { name: 'Select line 1', exact: true }).click();
    await page.locator('input[name="reason"]').first().click();
  } else if (label.includes('predict the fix')) {
    await page.locator('input[name="fix"]').first().click();
  } else if (label.includes('trace')) {
    await page.locator('input[name="choice"]').first().click();
  } else if (label.includes('summarize')) {
    await page.getByLabel(/Describe what this does/i).fill('A short valid summary of the code.');
  } else {
    throw new Error(`Unrecognized exercise type label: "${label}"`);
  }

  await page.getByRole('button', { name: 'Check answer' }).click();

  // The boundary fallback, NOT a blank page: the skip prompt is visible and
  // the app root still has content.
  const skipButton = page.getByRole('button', { name: 'Skip this exercise' });
  await expect(skipButton).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/Something went wrong showing this exercise/)).toBeVisible();

  // Continuing works: skipping advances to the next exercise (its answer UI)
  // or to session complete -- never a dead end.
  await skipButton.click();
  // Either the next exercise's answer UI, or -- if that was the last one --
  // the Dashboard's completed state. NOT "Session complete": no such screen
  // exists (see session.spec.ts's header). That dead branch was harmless only
  // because the first branch always matched; had the session actually ended
  // here it would have failed for an invented reason.
  await expect(
    page
      .getByRole('button', { name: 'Check answer' })
      .or(page.getByRole('link', { name: "Review today's session" })),
  ).toBeVisible({ timeout: 15_000 });
});
