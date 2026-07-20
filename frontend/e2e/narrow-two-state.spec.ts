import path from 'node:path';

import { expect, test, type Page } from '@playwright/test';

import { FIXTURE_SESSION, stubViewerRoutes } from './_viewerFixtures';

// D-134: the two full-screen narrow states, verified across every viewport we
// support, both states, all three types.
//
// The bottom sheet these replace passed its own tests and still failed by hand
// in ten minutes, because those tests asserted the sheet's behaviour rather
// than whether the screen was USABLE. These assert usability directly: code
// non-empty, toggle reachable, submit reachable without scrolling, no option
// clipped.

const SHOTS = process.env.VIEWER_SHOTS_DIR ?? 'current';

const VIEWPORTS = [
  { n: '375x667', w: 375, h: 667 },
  { n: '390x844', w: 390, h: 844 },
  { n: '400x670', w: 400, h: 670 },
  { n: '400x920', w: 400, h: 920 },
  { n: '430x932', w: 430, h: 932 },
  { n: '360x640', w: 360, h: 640 },
  { n: '667x375', w: 667, h: 375 },
];

const TYPES = [
  { name: 'spot_the_bug', i: 0, optionSelector: 'input[name="reason"]' },
  { name: 'trace', i: 1, optionSelector: 'input[name="choice"]' },
  { name: 'predict_the_fix', i: 2, optionSelector: 'input[name="fix"]' },
];

// Long enough to overflow every viewport.
const LONG = Array.from({ length: 45 }, (_, i) => `    step_${i} = compute_total(${i})`).join('\n');
const CODE = `def run():\n${LONG}\n    return step_0`;

function sessionFor(index: number) {
  const s = JSON.parse(JSON.stringify(FIXTURE_SESSION));
  s.exercises = [s.exercises[index]];
  s.exercises[0].payload.code = CODE;
  s.exercises[0].payload.documents = [{ id: 'primary', role: 'primary', code: CODE, language: 'python' }];
  return s;
}

const readingPane = (page: Page) => page.locator('[data-pane="reading"]');
const answeringPane = (page: Page) => page.locator('[data-pane="answering"]');
const backToCode = (page: Page) => page.getByRole('button', { name: /Back to the code/ });
const toAnswer = (page: Page) => readingPane(page).getByRole('button', { name: /Tap the buggy line|pick a reason|Answer|Review your answer/ });

/** Fully inside the viewport, not merely present in the DOM. */
async function isFullyOnScreen(page: Page, locator: ReturnType<Page['locator']>) {
  const box = await locator.boundingBox();
  if (!box) return false;
  const vp = page.viewportSize()!;
  return box.y >= -0.5 && box.x >= -0.5 && box.y + box.height <= vp.height + 0.5 && box.x + box.width <= vp.width + 0.5;
}

async function gotoAnswering(page: Page, index: number) {
  await stubViewerRoutes(page, { session: sessionFor(index) });
  await page.goto('/session');
  await page.locator('[data-line="1"]').first().waitFor({ timeout: 15_000 });
  await toAnswer(page).click();
  await expect(answeringPane(page)).toHaveAttribute('data-active', 'true');
}

for (const vp of VIEWPORTS) {
  test.describe(`${vp.n}`, () => {
    test.use({ viewport: { width: vp.w, height: vp.h } });

    for (const t of TYPES) {
      test(`${t.name}: both states are usable`, async ({ page }) => {
        await stubViewerRoutes(page, { session: sessionFor(t.i) });
        await page.goto('/session');
        await page.locator('[data-line="1"]').first().waitFor({ timeout: 15_000 });

        // ---- READING STATE ----
        await expect(readingPane(page)).toHaveAttribute('data-active', 'true');

        // Code renders, non-empty.
        const codeRows = await page.evaluate(() => {
          const rows = Array.from(document.querySelectorAll<HTMLElement>('[data-line]'));
          const scroller = document.querySelector<HTMLElement>('.overflow-y-auto');
          if (!scroller) return 0;
          const s = scroller.getBoundingClientRect();
          return rows.filter((r) => {
            const b = r.getBoundingClientRect();
            return b.height > 0.5 && b.bottom > s.top + 0.5 && b.top < s.bottom - 0.5;
          }).length;
        });
        expect(codeRows, `no code visible in reading state at ${vp.n}/${t.name}`).toBeGreaterThanOrEqual(1);

        // The toggle out of reading is on screen.
        expect(await isFullyOnScreen(page, toAnswer(page)), 'reading toggle off screen').toBe(true);

        await page.screenshot({
          path: path.join('viewer-shots', SHOTS, vp.n, `${t.name}-reading.png`),
        });

        // ---- ANSWERING STATE ----
        await toAnswer(page).click();
        await expect(answeringPane(page)).toHaveAttribute('data-active', 'true');

        // The way back is on screen...
        expect(await isFullyOnScreen(page, backToCode(page)), 'back-to-code off screen').toBe(true);
        // ...and submit is reachable WITHOUT scrolling past the options.
        const submit = page.getByRole('button', { name: /Check answer|Checking/ });
        expect(await isFullyOnScreen(page, submit), 'submit not reachable without scrolling').toBe(true);

        // No option is clipped: each one can be brought fully into view inside
        // the answer scroll region.
        const options = page.locator(t.optionSelector);
        const count = await options.count();
        expect(count, 'no options rendered').toBeGreaterThan(0);
        for (let i = 0; i < count; i += 1) {
          const label = options.nth(i).locator('xpath=ancestor::label[1]');
          await label.scrollIntoViewIfNeeded();
          const clipped = await label.evaluate((el) => {
            const scroller = el.closest('[data-answer-scroll]') as HTMLElement | null;
            if (!scroller) return 'no scroller';
            const b = el.getBoundingClientRect();
            const s = scroller.getBoundingClientRect();
            // Fully inside the scroll viewport after being scrolled to.
            if (b.top < s.top - 1 || b.bottom > s.bottom + 1) return `vertically clipped`;
            if (b.left < s.left - 1 || b.right > s.right + 1) return `horizontally clipped`;
            return null;
          });
          expect(clipped, `option ${i + 1} clipped at ${vp.n}/${t.name}`).toBeNull();
        }

        // Captured at rest, before the scroll checks below, so the shot shows
        // the state the reader actually arrives in.
        await page.screenshot({
          path: path.join('viewer-shots', SHOTS, vp.n, `${t.name}-answering.png`),
        });

        // Submit stays reachable with the options scrolled to the bottom.
        await page.locator('[data-answer-scroll]').evaluate((el) => el.scrollTo(0, el.scrollHeight));
        expect(await isFullyOnScreen(page, submit), 'submit lost after scrolling options').toBe(true);
        expect(await isFullyOnScreen(page, backToCode(page)), 'back-to-code lost after scrolling').toBe(true);

      });
    }
  });
}

// ---- the three toggle conditions, as acceptance tests ----

test.describe('toggle conditions', () => {
  test.use({ viewport: { width: 375, height: 667 } });

  test('scroll position is preserved on BOTH sides of a switch', async ({ page }) => {
    await gotoAnswering(page, 2); // predict_the_fix: tallest options

    // Scroll the options, then leave and come back.
    await page.locator('[data-answer-scroll]').evaluate((el) => el.scrollTo(0, 120));
    const answerScrollBefore = await page.locator('[data-answer-scroll]').evaluate((el) => el.scrollTop);
    expect(answerScrollBefore).toBeGreaterThan(0);

    await backToCode(page).click();
    await expect(readingPane(page)).toHaveAttribute('data-active', 'true');

    // Scroll the CODE, then switch away and back.
    const codeScroller = page.locator('[data-pane="reading"] .overflow-y-auto').first();
    await codeScroller.evaluate((el) => el.scrollTo(0, 200));
    const codeScrollBefore = await codeScroller.evaluate((el) => el.scrollTop);
    expect(codeScrollBefore).toBeGreaterThan(0);

    await toAnswer(page).click();
    const answerScrollAfter = await page.locator('[data-answer-scroll]').evaluate((el) => el.scrollTop);
    expect(answerScrollAfter, 'answer scroll lost across a switch').toBeCloseTo(answerScrollBefore, 0);

    await backToCode(page).click();
    const codeScrollAfter = await codeScroller.evaluate((el) => el.scrollTop);
    expect(codeScrollAfter, 'code scroll lost across a switch').toBeCloseTo(codeScrollBefore, 0);
  });

  test('the toggle is visible at every scroll position, in both states', async ({ page }) => {
    await stubViewerRoutes(page, { session: sessionFor(2) });
    await page.goto('/session');
    await page.locator('[data-line="1"]').first().waitFor({ timeout: 15_000 });

    const codeScroller = page.locator('[data-pane="reading"] .overflow-y-auto').first();
    for (const pos of ['top', 'middle', 'bottom'] as const) {
      await codeScroller.evaluate((el, p) => {
        el.scrollTo(0, p === 'top' ? 0 : p === 'middle' ? el.scrollHeight / 2 : el.scrollHeight);
      }, pos);
      expect(await isFullyOnScreen(page, toAnswer(page)), `reading toggle hidden at ${pos}`).toBe(true);
    }

    await toAnswer(page).click();
    const answerScroller = page.locator('[data-answer-scroll]');
    for (const pos of ['top', 'middle', 'bottom'] as const) {
      await answerScroller.evaluate((el, p) => {
        el.scrollTo(0, p === 'top' ? 0 : p === 'middle' ? el.scrollHeight / 2 : el.scrollHeight);
      }, pos);
      expect(await isFullyOnScreen(page, backToCode(page)), `back-to-code hidden at ${pos}`).toBe(true);
      expect(
        await isFullyOnScreen(page, page.getByRole('button', { name: /Check answer|Checking/ })),
        `submit hidden at ${pos}`,
      ).toBe(true);
    }
  });

  test('the switch is instant and does not slide', async ({ page }) => {
    await stubViewerRoutes(page, { session: sessionFor(1) });
    await page.goto('/session');
    await page.locator('[data-line="1"]').first().waitFor({ timeout: 15_000 });

    // Timed IN THE PAGE, not across a Playwright round trip. Measuring
    // click()->expect() measures the harness (~100-300ms of protocol traffic),
    // not the switch; the first version of this test failed on that overhead
    // while the switch itself was a single frame.
    const elapsed = await page.evaluate(async () => {
      const btn = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-pane="reading"] button')).find((b) =>
        /Tap the buggy line|pick a reason|Answer|Review your answer/.test(b.textContent ?? ''),
      );
      const pane = document.querySelector('[data-pane="answering"]');
      if (!btn || !pane) return -1;
      return await new Promise<number>((resolve) => {
        const start = performance.now();
        const observer = new MutationObserver(() => {
          if (pane.getAttribute('data-active') === 'true') {
            observer.disconnect();
            // Wait one frame so the paint that follows the flip is included.
            requestAnimationFrame(() => resolve(performance.now() - start));
          }
        });
        observer.observe(pane, { attributes: true, attributeFilter: ['data-active'] });
        btn.click();
      });
    });
    expect(elapsed, 'switch not measurable').toBeGreaterThanOrEqual(0);
    expect(elapsed, `switch took ${Math.round(elapsed)}ms, over the 150ms budget`).toBeLessThan(150);
    await expect(answeringPane(page)).toHaveAttribute('data-active', 'true');

    // No slide: neither pane animates or transitions a transform.
    const motion = await page.evaluate(() => {
      return Array.from(document.querySelectorAll<HTMLElement>('[data-pane]')).map((el) => {
        const cs = getComputedStyle(el);
        return {
          // transition-property's CSS initial value is literally `all`, so
          // asserting on the property list flags every element in the
          // document. What decides whether anything MOVES is the duration.
          transitionDuration: cs.transitionDuration,
          animationName: cs.animationName,
          transform: cs.transform,
        };
      });
    });
    for (const m of motion) {
      expect(m.animationName === 'none' || m.animationName === '').toBe(true);
      // Every declared duration is zero: nothing eases, nothing slides.
      expect(m.transitionDuration.split(',').every((d) => parseFloat(d) === 0)).toBe(true);
      expect(m.transform === 'none' || m.transform === 'matrix(1, 0, 0, 1, 0, 0)').toBe(true);
    }
  });

  test('spot_the_bug: tapping a line carries the selection over, and back preserves it', async ({ page }) => {
    await stubViewerRoutes(page, { session: sessionFor(0) });
    await page.goto('/session');
    await page.locator('[data-line="1"]').first().waitFor({ timeout: 15_000 });

    await page.getByRole('button', { name: 'Select line 4', exact: true }).click();

    // Tapping a line moved us to answering, with the line selected.
    await expect(answeringPane(page)).toHaveAttribute('data-active', 'true');
    await expect(answeringPane(page).getByText(/Line 4 selected|Ready to check|Choose an answer/)).toBeVisible();

    await backToCode(page).click();
    await expect(page.getByRole('button', { name: 'Select line 4', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    );

    // ...and it survives a second round trip.
    await toAnswer(page).click();
    await backToCode(page).click();
    await expect(page.getByRole('button', { name: 'Select line 4', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  test('the trace pinned line appears only after a selection exists', async ({ page }) => {
    await stubViewerRoutes(page, { session: sessionFor(1) });
    await page.goto('/session');
    await page.locator('[data-line="1"]').first().waitFor({ timeout: 15_000 });

    // First read: the code is alone. No empty bar.
    await expect(page.locator('[data-pinned-selection]')).toHaveCount(0);

    await toAnswer(page).click();
    await page.locator('input[name="choice"]').first().check();
    await backToCode(page).click();

    // Now there is something to verify against the code.
    await expect(page.locator('[data-pinned-selection]')).toBeVisible();
  });
});
