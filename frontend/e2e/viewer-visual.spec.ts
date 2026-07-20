import path from 'node:path';

import { expect, test, type Page } from '@playwright/test';

import { enterAnsweringState, stubViewerRoutes } from './_viewerFixtures';

// Visual-regression harness for the viewer (D-129, extended for D-130 mobile).
//
// Captures the answer and reveal states of all three live types at every
// viewport we support, into a named directory, so the same run before and
// after a change produces two directories a byte comparison can hold against
// each other. VIEWER_SHOTS_DIR names the output ("before" / "after").
//
// Hermetic: _viewerFixtures stubs every route, so this needs no stack and can
// never be affected by which exercises the sampler happened to pick.

// Default is 'current', NOT 'before': defaulting to the baseline name meant
// any plain `npx playwright test` silently overwrote the baseline with
// post-change output, and a comparison against it then reported a false
// 'identical'. A baseline must only ever be written on purpose.
const OUT = process.env.VIEWER_SHOTS_DIR ?? 'current';

// Breakpoint on AVAILABLE WIDTH, not device class -- so the viewport list is
// widths we must work at, not phones we have heard of.
//   1280x800  desktop, must not change
//   375x667   portrait phone, the archetypal session
//   360x480   the narrowest we claim to support
//   667x375   landscape phone: 667 is a good code-reading width, short height
export const VIEWPORTS = [
  { name: '1280x800', width: 1280, height: 800 },
  { name: '375x667', width: 375, height: 667 },
  // 400x844: the viewport the D-132 problems were reported at.
  { name: '400x844', width: 400, height: 844 },
  { name: '360x480', width: 360, height: 480 },
  { name: '667x375', width: 667, height: 375 },
];

interface Step {
  name: string;
  answer: (page: Page) => Promise<void>;
}

const STEPS: Step[] = [
  {
    name: 'spot_the_bug',
    answer: async (page) => {
      // D-134: the line tap happens in the READING state and is itself
      // what carries you into answering, so it must come first.
      await page.getByRole('button', { name: 'Select line 4', exact: true }).click();
      await enterAnsweringState(page);
      await page.locator('input[name="reason"]').first().click();
    },
  },
  {
    name: 'trace',
    answer: async (page) => {
      await enterAnsweringState(page);
      await page.locator('input[name="choice"]').first().click();
    },
  },
  {
    name: 'predict_the_fix',
    answer: async (page) => {
      await enterAnsweringState(page);
      await page.locator('input[name="fix"]').first().click();
    },
  },
];

async function settle(page: Page) {
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);
}


for (const vp of VIEWPORTS) {
  test.describe(`viewport ${vp.name}`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    test('the three live types and their reveals', async ({ page }) => {
      const shotDir = path.join('viewer-shots', OUT, vp.name);
      await stubViewerRoutes(page);
      await page.goto('/session');

      for (const [i, step] of STEPS.entries()) {
        await expect(page.locator('span.capitalize').first()).toBeVisible({ timeout: 15_000 });
        await settle(page);
        // Resting state: what the reader sees first. On narrow this is the
        // whole point -- code owning the viewport, answer controls at rest.
        await page.screenshot({ path: path.join(shotDir, `${i + 1}-${step.name}-answer.png`), fullPage: true });

        await step.answer(page);
        await page.getByRole('button', { name: 'Check answer' }).click();

        await expect(page.getByRole('button', { name: /Next|Finish/ })).toBeVisible({ timeout: 15_000 });
        await settle(page);
        await page.screenshot({ path: path.join(shotDir, `${i + 1}-${step.name}-reveal.png`), fullPage: true });

        if (i < STEPS.length - 1) {
          await page.getByRole('button', { name: /Next|Finish/ }).click();
        }
      }
    });
  });
}
