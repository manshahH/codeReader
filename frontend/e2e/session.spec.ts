import { expect, test } from '@playwright/test';

import { localStackIsUp, seedAuthCookie, STACK_REQUIRED } from './_seed';

// Auth: no real GitHub OAuth here. seedAuthCookie() seeds a fresh user and
// issues a refresh token through the exact same app.auth.tokens code the real
// OAuth callback uses, and sets it as the `rt` cookie -- the SPA's normal POST
// /auth/refresh flow (RootGate) takes it from there. This is the "login (seed)"
// step from the milestone's success criteria, not a bypass of the auth code.

// ROOT-CAUSED AND FIXED (2026-07-18), closing the second half of D-119.
//
// This spec was never testing a product bug. It asserted a "Session complete"
// screen, and that screen DOES NOT EXIST anywhere in frontend/src -- its absence
// is a deliberate, documented decision (HANDOFF, docs/10: Session.tsx redirects
// to the Dashboard once the last exercise is answered, and building a real
// session-complete screen is its own piece of work). So the loop's break
// condition never fired, the run walked one iteration past the last exercise,
// /session had already redirected to the Dashboard, and `span.capitalize` was
// missing. The spec failed on a selector four steps from its actual mistake.
//
// The "early completion" reading was wrong, and the misreading was mine: the
// dashboard's "1/5" is correct_count/exercise_count (Dashboard.tsx:203), i.e.
// ONE CORRECT out of five, not one attempted out of five. The browser log shows
// five POST /v1/attempts for a five-slot session. Backend, dashboard and
// daily_sessions agreed the whole time; a direct measurement confirmed it
// (5 slots persisted, 5 exercises served, before and after attempts).
//
// Fixed by asserting the completion signal this app actually has: the redirect
// to the Dashboard plus its completed state. A session of 3, 4 or 5 exercises is
// all normal (sampler MIN_SLOTS=3, MAX_NON_BOSS_SLOTS=4 plus an optional boss),
// so the loop bounds on leaving /session rather than on any fixed count.

test('full session: login (seed) -> one of each type -> reveal -> complete', async ({ page, context }) => {
  const MAX_EXERCISES = 8; // sampler may add a boss slot; never more than MIN_SLOTS..MAX_NON_BOSS_SLOTS+1
  page.on('console', (msg) => console.log(`[browser:${msg.type()}] ${msg.text()}`));
  test.skip(!(await localStackIsUp()), STACK_REQUIRED);

  page.on('pageerror', (err) => console.log(`[pageerror] ${err.message}`));
  page.on('requestfailed', (req) => console.log(`[requestfailed] ${req.url()} ${req.failure()?.errorText}`));
  page.on('response', (res) => {
    if (res.url().includes('/v1/')) console.log(`[response] ${res.status()} ${res.url()}`);
  });

  await seedAuthCookie(context);

  // "/" is the dashboard for an onboarded user (RootGate, D-98/D-99), not an
  // auto-redirect to /session -- entering the session is the user's own click
  // from the dashboard's CTA. (Pre-M9 this test asserted "/" === /session,
  // which is why the whole M6 smoke suite had been red on a benign routing
  // change; fixed here without dropping any coverage.)
  // The dashboard CTA is the ONE deliberate click that starts a session (D-111):
  // it lands straight in the player, never on a second "are you sure" screen.
  await page.goto('/');
  await page.getByRole('link', { name: 'Enter sandbox' }).click({ timeout: 15_000 });
  await expect(page).toHaveURL(/\/session$/, { timeout: 15_000 });

  const seenTypes = new Set<string>();
  let skipped = false;

  for (let i = 0; i < MAX_EXERCISES; i++) {
    // There is no session-complete SCREEN to look for (see the header note):
    // finishing the last exercise redirects to the Dashboard, so leaving
    // /session IS the completion signal.
    if (!/\/session$/.test(new URL(page.url()).pathname)) break;

    const typeLabel = page.locator('span.capitalize').first();
    await expect(typeLabel).toBeVisible({ timeout: 15_000 });
    const label = (await typeLabel.textContent())?.toLowerCase().trim() ?? '';
    seenTypes.add(label);

    // Skip exactly one non-summarize exercise, first opportunity only, so
    // the rest of the run still exercises the normal answer path.
    if (!skipped && !label.includes('summarize')) {
      skipped = true;
      await page.getByRole('button', { name: "I don't know" }).click();
      // Anchored regex, not a plain-string getByText: the latter is a
      // case-insensitive substring match and can collide with the word
      // "skipped" inside an exercise's own explanation prose.
      await expect(page.getByText(/^Skipped\.$/)).toBeVisible({ timeout: 25_000 });
      await page.getByRole('button', { name: 'Next' }).click();
      continue;
    }

    if (label.includes('spot the bug')) {
      // Selecting a specific line/reason text assumes one fixed seeded
      // exercise; the live pool has more than that, so pick *a* valid
      // answer (any line, first reason) rather than depend on its content --
      // the assertion below only needs a verdict to render.
      await page.getByRole('button', { name: 'Select line 1', exact: true }).click();
      await page.locator('input[name="reason"]').first().click();
    } else if (label.includes('predict the fix')) {
      // Choices render as full code blocks (no plain-text accessible name),
      // so select by the radio group's name rather than by label text --
      // `name="fix"` is unique to PredictTheFixAnswer (trace uses "choice").
      await page.locator('input[name="fix"]').first().click();
    } else if (label.includes('trace')) {
      await page.locator('input[name="choice"]').first().click();
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

  // The exact type mix is sampled from the live pool and not guaranteed to
  // contain any one type on a given day, so requiring predict_the_fix here was
  // ~1-in-5 flaky. The smoke's real invariant is that a full session of
  // WHATEVER it served plays all the way through reveal to completion;
  // deterministic per-type UI coverage (predict_the_fix included) lives in its
  // own hermetic spec (predict-the-fix.spec.ts), not in this sampling-driven run.
  expect(seenTypes.size, 'session served no exercises').toBeGreaterThan(0);

  // Completion, as this app actually expresses it: the player redirects to the
  // Dashboard, which flips to its completed state and offers the review link
  // instead of the "Enter sandbox" CTA.
  // baseURL-relative, not a hardcoded :5173. The port is configuration (the
  // config's baseURL, or E2E_BASE_URL when pointing at an existing server), so
  // hardcoding it made this assertion fail on any other port -- which is how it
  // failed while the suite ran against a harness server, and would fail in CI
  // the moment the dev-server port moved. Playwright resolves a string URL
  // against baseURL, so "/" means "the app root, wherever that is".
  await expect(page).toHaveURL('/', { timeout: 15_000 });
  await expect(page.getByText('Completed', { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('link', { name: "Review today's session" })).toBeVisible();
});
