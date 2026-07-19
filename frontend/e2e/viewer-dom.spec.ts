import fs from 'node:fs';
import path from 'node:path';

import { expect, test, type Page } from '@playwright/test';

import { enterAnsweringState, stubViewerRoutes } from './_viewerFixtures';

// Companion to viewer-visual: dumps the rendered DOM of each state instead of
// a picture of it. A pixel diff says something moved; this says what.
//
// This is the instrument that proves "desktop above the breakpoint must not
// change": run with VIEWER_DOM_DIR=before against the pre-change tree and
// =after against the changed one, then diff the directories. Identical markup
// at 1280x800 is a far stronger claim than identical pixels.

// See the note in viewer-visual.spec.ts: never default to the baseline name.
const OUT = process.env.VIEWER_DOM_DIR ?? 'current';

const VIEWPORTS = [
  { name: '1280x800', width: 1280, height: 800 },
  { name: '375x667', width: 375, height: 667 },
];

const STEPS = [
  {
    name: 'spot_the_bug',
    answer: async (page: Page) => {
      // D-134: the line tap happens in the READING state and is itself
      // what carries you into answering, so it must come first.
      await page.getByRole('button', { name: 'Select line 4', exact: true }).click();
      await enterAnsweringState(page);
      await page.locator('input[name="reason"]').first().click();
    },
  },
  {
    name: 'trace',
    answer: async (page: Page) => {
      await enterAnsweringState(page);
      await page.locator('input[name="choice"]').first().click();
    },
  },
  {
    name: 'predict_the_fix',
    answer: async (page: Page) => {
      await enterAnsweringState(page);
      await page.locator('input[name="fix"]').first().click();
    },
  },
];

for (const vp of VIEWPORTS) {
  test.describe(`viewport ${vp.name}`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    test('dump the rendered DOM of the three types and their reveals', async ({ page }) => {
      const outDir = path.join('viewer-dom', OUT, vp.name);
      fs.mkdirSync(outDir, { recursive: true });
      await stubViewerRoutes(page);
      await page.goto('/session');

      for (const [i, step] of STEPS.entries()) {
        await expect(page.locator('span.capitalize').first()).toBeVisible({ timeout: 15_000 });
        await page.waitForLoadState('networkidle');
        fs.writeFileSync(
          path.join(outDir, `${i + 1}-${step.name}-answer.html`),
          await page.locator('#root').innerHTML(),
        );

        await step.answer(page);
        await page.getByRole('button', { name: 'Check answer' }).click();
        await expect(page.getByRole('button', { name: /Next|Finish/ })).toBeVisible({ timeout: 15_000 });
        await page.waitForLoadState('networkidle');
        fs.writeFileSync(
          path.join(outDir, `${i + 1}-${step.name}-reveal.html`),
          await page.locator('#root').innerHTML(),
        );

        if (i < STEPS.length - 1) {
          await page.getByRole('button', { name: /Next|Finish/ }).click();
        }
      }
    });
  });
}
