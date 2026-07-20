import path from 'node:path';

import { expect, test, type Page } from '@playwright/test';

import { FIXTURE_REVEALS, FIXTURE_SESSION, stubViewerRoutes } from './_viewerFixtures';

// The two surfaces the earlier narrow-viewport audit never reached: the dispute
// modal (never opened) and the review screen (only ever seen empty). Both are
// measured here at the two widths the audit used, so the gap closes with
// evidence rather than with a note saying it was probably fine.

const SHOTS = process.env.VIEWER_SHOTS_DIR ?? 'current';

const WIDTHS = [
  { name: '375x667', width: 375, height: 667 },
  { name: '360x480', width: 360, height: 480 },
];

/** A non-empty review payload. The review row shape is NOT the session payload
 * shape (SessionReviewExercise carries a bare `code` string and a `reveal`), so
 * this cannot be built by reusing the session fixture wholesale. */
const REVIEW_RESPONSE = {
  session_date: '2026-07-19',
  exercises: [
    {
      slot: 1,
      exercise_id: FIXTURE_SESSION.exercises[0].exercise_id,
      version: 1,
      type: 'spot_the_bug',
      concepts: ['arithmetic'],
      code: FIXTURE_SESSION.exercises[0].payload.code,
      context_note: FIXTURE_SESSION.exercises[0].payload.context_note,
      answer: { line: 2, reason_id: 'r1' },
      verdict: 'incorrect',
      reveal: FIXTURE_REVEALS.spot_the_bug,
    },
    {
      slot: 2,
      exercise_id: FIXTURE_SESSION.exercises[1].exercise_id,
      version: 1,
      type: 'trace',
      concepts: ['dicts'],
      code: FIXTURE_SESSION.exercises[1].payload.code,
      context_note: FIXTURE_SESSION.exercises[1].payload.context_note,
      answer: { choice_id: 'c1' },
      verdict: 'correct',
      reveal: FIXTURE_REVEALS.trace,
    },
  ],
};

/** Nothing may exceed the viewport horizontally, measured per element rather
 * than only on documentElement -- an overflowing child inside an
 * overflow-hidden ancestor clips content while leaving the document clean. */
async function assertNoOverflow(page: Page, label: string) {
  const offenders = await page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const bad: { tag: string; cls: string; right: number }[] = [];
    document.querySelectorAll<HTMLElement>('body *').forEach((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      if (rect.right > vw + 1 || rect.left < -1) {
        bad.push({ tag: el.tagName, cls: el.className?.toString().slice(0, 80) ?? '', right: Math.round(rect.right) });
      }
    });
    return bad;
  });
  expect(offenders, `${label}: elements overflowing the viewport`).toEqual([]);
}

/** Every interactive control must clear the touch floor in at least the
 * dimension it is reached in. Buttons and links are measured on height, which
 * is where a cramped modal actually fails. */
async function assertTouchTargets(page: Page, label: string, root = 'body') {
  const small = await page.evaluate((sel) => {
    const bad: { text: string; w: number; h: number }[] = [];
    document.querySelectorAll<HTMLElement>(`${sel} button, ${sel} a[href], ${sel} input[type="radio"]`).forEach((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      if (rect.height < 44) {
        bad.push({ text: (el.textContent ?? el.getAttribute('aria-label') ?? '').trim().slice(0, 40), w: Math.round(rect.width), h: Math.round(rect.height) });
      }
    });
    return bad;
  }, root);
  // Reported, not asserted to zero -- see the report. Inline text links inside
  // prose legitimately sit below the floor, and forcing them to 44px would
  // wreck the reading measure that is the product.
  return small;
}

for (const vp of WIDTHS) {
  test.describe(`uncovered surfaces at ${vp.name}`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    test('the dispute modal opens, fits, and is operable', async ({ page }) => {
      await stubViewerRoutes(page);
      await page.goto('/session');

      // Reach a reveal, which is where the report control lives.
      await expect(page.getByRole('button', { name: 'Select line 4', exact: true })).toBeVisible({ timeout: 15_000 });
      await page.getByRole('button', { name: 'Select line 4', exact: true }).click();
      await page.locator('input[name="reason"]').first().click();
      await page.getByRole('button', { name: 'Check answer' }).click();
      await expect(page.getByRole('button', { name: /Next|Finish/ })).toBeVisible({ timeout: 15_000 });

      // THE GAP: this modal had never been opened at a narrow width.
      await page.getByRole('button', { name: 'Something wrong with this exercise?' }).click();

      const dialog = page.getByRole('dialog');
      await expect(dialog).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Report a problem' })).toBeVisible();

      await assertNoOverflow(page, `dispute modal ${vp.name}`);

      // The dialog fits the viewport vertically or scrolls internally; either
      // is fine, being taller than the screen with no way to reach Send is not.
      const box = (await dialog.boundingBox())!;
      const reachable = box.height <= vp.height || (await dialog.evaluate((el) => el.scrollHeight > el.clientHeight));
      expect(reachable, 'dialog is taller than the viewport and does not scroll').toBeTruthy();

      // Operable: pick a reason, and the submit control is present and hittable.
      await dialog.locator('input[type="radio"]').first().check();
      const send = dialog.getByRole('button', { name: /Send|Submit|Report/ }).last();
      await expect(send).toBeVisible();
      await expect(send).toBeEnabled();

      await page.screenshot({ path: path.join('viewer-shots', SHOTS, vp.name, 'dispute-modal.png'), fullPage: true });

      // Escape / close returns to the reveal rather than trapping the reader.
      await dialog.getByRole('button', { name: 'Close' }).click();
      await expect(dialog).toBeHidden();
    });

    test('the review screen renders a real session', async ({ page }) => {
      await stubViewerRoutes(page);
      // THE OTHER GAP: review had only ever been seen in its empty state, so
      // nothing had measured it with actual code, verdicts and explanations in it.
      await page.route('**/v1/session/today/review', (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(REVIEW_RESPONSE) }),
      );

      await page.goto('/review');

      await expect(page.getByText(/Review —/)).toBeVisible({ timeout: 15_000 });
      // Real content, not the empty state.
      await expect(page.getByText('Nothing to review yet today.')).toHaveCount(0);
      await expect(page.locator('[data-line="1"]').first().or(page.locator('pre').first())).toBeVisible();

      await assertNoOverflow(page, `review ${vp.name}`);

      await page.screenshot({ path: path.join('viewer-shots', SHOTS, vp.name, 'review-populated.png'), fullPage: true });

      // Paging through the reviewed exercises works at this width.
      await page.getByRole('button', { name: 'Next' }).click();
      await expect(page.getByText(/2 \/ 2/)).toBeVisible();
      await assertNoOverflow(page, `review page 2 ${vp.name}`);

      await page.screenshot({ path: path.join('viewer-shots', SHOTS, vp.name, 'review-populated-2.png'), fullPage: true });

      const small = await assertTouchTargets(page, `review ${vp.name}`);
      // Recorded in the run output so the report can state it honestly.
      console.log(`[touch-audit] review ${vp.name} controls under 44px high: ${JSON.stringify(small)}`);
    });
  });
}
