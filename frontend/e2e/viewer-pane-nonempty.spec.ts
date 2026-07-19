import { expect, test, type Page } from '@playwright/test';

import { FIXTURE_SESSION, stubViewerRoutes } from './_viewerFixtures';

// D-133: the code pane must never render empty.
//
// The reported failure was an empty code pane -- a black void with the answer
// bar below it. Root cause: the row-snapping hook wrote a max-height derived
// from a measurement of an ancestor whose own height depended on that
// max-height. One zero-height moment (which happens for real during a phase or
// exercise swap) wrote 0px, which collapsed the scroller, which collapsed the
// ancestor, which made the next measurement 0 as well. Absorbing state: the
// pane never came back.
//
// A snapping rule that can snap to zero is worse than a half row, so these
// tests assert the floor rather than the tidiness.

const VIEWPORTS = [
  { n: '375x667', w: 375, h: 667 },
  { n: '390x844', w: 390, h: 844 },
  { n: '400x670', w: 400, h: 670 },
  { n: '400x920', w: 400, h: 920 },
  { n: '430x932', w: 430, h: 932 },
  { n: '360x640', w: 360, h: 640 },
  { n: '667x375', w: 667, h: 375 },
  // Deliberately hostile: shorter than anything we claim to support, and short
  // enough that 44px tap rows plus the sticky header plus padding exceed it.
  { n: '320x400 (hostile)', w: 320, h: 400 },
  { n: '360x320 (hostile)', w: 360, h: 320 },
];

const TYPES = [
  { name: 'spot_the_bug', i: 0 },
  { name: 'trace', i: 1 },
  { name: 'predict_the_fix', i: 2 },
];

// Long enough to overflow every viewport, with one very long line that wraps
// to several rows -- the case where "no whole row fits" is reachable.
const LONG = Array.from({ length: 50 }, (_, i) =>
  i === 3
    ? '    result = compute_totals(basket, discount_policy, currency="GBP", rounding="half-even", audit=True)'
    : `    step_${i} = compute_total(${i})`,
).join('\n');
const CODE = `def run():\n${LONG}\n    return step_0`;

function sessionFor(index: number) {
  const s = JSON.parse(JSON.stringify(FIXTURE_SESSION));
  s.exercises = [s.exercises[index]];
  s.exercises[0].payload.code = CODE;
  s.exercises[0].payload.documents = [{ id: 'primary', role: 'primary', code: CODE, language: 'python' }];
  return s;
}

async function rowsInView(page: Page) {
  return page.evaluate(() => {
    const rows = Array.from(document.querySelectorAll<HTMLElement>('[data-line]'));
    const scroller = document.querySelector<HTMLElement>('.overflow-y-auto');
    if (!scroller) return { inView: 0, paneHeight: 0 };
    const s = scroller.getBoundingClientRect();
    const inView = rows.filter((r) => {
      const b = r.getBoundingClientRect();
      return b.height > 0.5 && b.bottom > s.top + 0.5 && b.top < s.bottom - 0.5;
    }).length;
    return { inView, paneHeight: Math.round(s.height) };
  });
}

for (const vp of VIEWPORTS) {
  test.describe(`code pane at ${vp.n}`, () => {
    test.use({ viewport: { width: vp.w, height: vp.h } });

    for (const t of TYPES) {
      test(`${t.name} renders at least one code row`, async ({ page }) => {
        await stubViewerRoutes(page, { session: sessionFor(t.i) });
        await page.goto('/session');
        await page.locator('[data-line="1"]').first().waitFor({ timeout: 15_000 });

        const { inView, paneHeight } = await rowsInView(page);
        expect(paneHeight, `pane collapsed at ${vp.n}/${t.name}`).toBeGreaterThan(0);
        expect(inView, `no code row visible at ${vp.n}/${t.name}`).toBeGreaterThanOrEqual(1);
      });
    }
  });
}

test.describe('the pane cannot latch shut', () => {
  test.use({ viewport: { width: 400, height: 920 } });

  test('a zero-height moment does not permanently collapse the code pane', async ({ page }) => {
    await stubViewerRoutes(page, { session: sessionFor(1) });
    await page.goto('/session');
    await page.locator('[data-line="1"]').first().waitFor({ timeout: 15_000 });

    const before = await rowsInView(page);
    expect(before.inView).toBeGreaterThan(0);

    // Exactly the condition that produced the void: the pane's container has
    // zero height for one frame, then comes back.
    await page.evaluate(() => {
      const el = document.querySelector<HTMLElement>('.overflow-y-auto')?.parentElement?.parentElement;
      if (el) el.style.display = 'none';
    });
    await page.waitForTimeout(150);
    await page.evaluate(() => {
      const el = document.querySelector<HTMLElement>('.overflow-y-auto')?.parentElement?.parentElement;
      if (el) el.style.display = '';
    });
    await page.waitForTimeout(500);

    const after = await rowsInView(page);
    expect(after.paneHeight, 'pane latched shut after a zero-height moment').toBeGreaterThan(0);
    expect(after.inView, 'no code row recovered after a zero-height moment').toBeGreaterThanOrEqual(1);
  });
});
