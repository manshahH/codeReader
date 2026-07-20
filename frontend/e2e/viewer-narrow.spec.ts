import { expect, test, type Page } from '@playwright/test';

import { FIXTURE_SESSION, stubViewerRoutes } from './_viewerFixtures';

// D-130: the narrow arrangement, measured rather than eyeballed.
//
// Every fixture here carries real `documents` payloads (see _viewerFixtures) --
// legacy-shaped fixtures are exactly what hid the predict_the_fix
// multi-document bug during D-129, where the screenshots looked perfect because
// the stub never exercised the shape the backend actually sends.

const NARROW = { width: 375, height: 667 };
const TINY = { width: 360, height: 480 };
const LANDSCAPE = { width: 667, height: 375 };

const LONG_LINE =
  'result = compute_totals(basket, discount_policy, currency="GBP", rounding="half-even", audit_trail=True)';

function sessionWith(code: string, index = 0) {
  const session = JSON.parse(JSON.stringify(FIXTURE_SESSION));
  session.exercises = [session.exercises[index]];
  session.exercises[0].payload.code = code;
  session.exercises[0].payload.documents = [
    { id: 'primary', role: 'primary', code, language: 'python' },
  ];
  return session;
}

async function gotoSession(page: Page, session?: unknown) {
  await stubViewerRoutes(page, session ? { session } : {});
  await page.goto('/session');
  await expect(page.locator('span.capitalize').first()).toBeVisible({ timeout: 15_000 });
}

test.describe('tap targets', () => {
  test.use({ viewport: NARROW });

  test('every line-number target reaches the touch floor and the screen edge', async ({ page }) => {
    await gotoSession(page);

    const buttons = page.getByRole('button', { name: /^Select line \d+$/ });
    const count = await buttons.count();
    expect(count).toBeGreaterThan(3);

    for (let i = 0; i < count; i += 1) {
      const box = (await buttons.nth(i).boundingBox())!;
      expect(box.width, `line ${i + 1} target width`).toBeGreaterThanOrEqual(44);
      // D-131: height too, now that the code line-height opens to the touch
      // floor below the breakpoint. This is reached by making the LINE taller,
      // never by padding the button -- padding would overlap the neighbouring
      // line, and a mistap selecting the wrong line is the one failure
      // spot_the_bug cannot have.
      expect(box.height, `line ${i + 1} target height`).toBeGreaterThanOrEqual(44);
      // And it starts at the screen edge: the dead page margin is hit area.
      expect(box.x, `line ${i + 1} target left edge`).toBeLessThanOrEqual(1);
    }
  });

  test('adjacent line targets do not overlap', async ({ page }) => {
    await gotoSession(page);

    const first = (await page.getByRole('button', { name: 'Select line 1', exact: true }).boundingBox())!;
    const second = (await page.getByRole('button', { name: 'Select line 2', exact: true }).boundingBox())!;

    // The invariant that forbids vertical padding on these buttons.
    expect(first.y + first.height).toBeLessThanOrEqual(second.y + 0.5);
  });
});

test.describe('navigation touch targets (D-131)', () => {
  test.use({ viewport: NARROW });

  test('navigation links clear the touch floor; prose links are left alone', async ({ page }) => {
    await gotoSession(page);

    // Navigation: chrome the reader taps to go somewhere.
    for (const name of ['Code Reader', 'Profile']) {
      const box = (await page.getByRole('link', { name, exact: true }).boundingBox())!;
      expect(box.height, `${name} nav link height`).toBeGreaterThanOrEqual(44);
    }

    // The line-number targets are navigation-adjacent and already covered
    // above; what must NOT have grown is prose. The context note is reading
    // material, and padding text inside it to 44px would wreck the measure.
    const noteHeight = await page
      .getByText('A checkout helper that applies a percentage discount to a basket.')
      .evaluate((el) => el.getBoundingClientRect().height);
    // Two clamped lines of body text, nowhere near a 44px-per-line block.
    expect(noteHeight).toBeLessThan(70);
  });

  test('the reason picker does not repeat the instruction the sheet already gave', async ({ page }) => {
    await gotoSession(page);

    // D-134: the instruction lives on the reading state's action button now,
    // where it is visible while the reader still has to act on it.
    await expect(page.getByRole('button', { name: /Tap the buggy line/ })).toBeVisible();

    await page.getByRole('button', { name: 'Select line 4', exact: true }).click();
    await expect(page.locator('[data-pane="answering"]')).toHaveAttribute('data-active', 'true');

    // ...and it is NOT repeated inside the raised sheet, where it would be
    // telling the reader to do the thing they just did. Hidden via CSS rather
    // than removed in JS, so the wide layout keeps it with no branch: display:
    // none is not announced by screen readers either, so "hidden" is the whole
    // claim.
    await expect(page.getByText('Tap the line number in the code where the bug is.')).toBeHidden();
  });
});

test.describe('no horizontal overflow, per container', () => {
  for (const [name, viewport] of [
    ['375x667', NARROW],
    ['360x480', TINY],
    ['667x375', LANDSCAPE],
  ] as const) {
    test.describe(name, () => {
      test.use({ viewport });

      test('the page does not scroll sideways and no element exceeds the viewport', async ({ page }) => {
        await gotoSession(page, sessionWith(`def checkout(basket):\n    ${LONG_LINE}\n    return result`));

        // Per-container, not just document width: a single overflowing child
        // inside an overflow-hidden ancestor leaves documentElement clean while
        // still clipping content the reader needs.
        const offenders = await page.evaluate(() => {
          const vw = document.documentElement.clientWidth;
          const bad: { tag: string; cls: string; right: number }[] = [];
          document.querySelectorAll<HTMLElement>('body *').forEach((el) => {
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return;
            // 1px tolerance for subpixel layout.
            if (rect.right > vw + 1 || rect.left < -1) {
              bad.push({ tag: el.tagName, cls: el.className?.toString().slice(0, 80) ?? '', right: Math.round(rect.right) });
            }
          });
          return bad;
        });
        expect(offenders, `elements overflowing ${name}`).toEqual([]);

        const scrollsSideways = await page.evaluate(
          () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        );
        expect(scrollsSideways, 'document scrolls horizontally').toBe(false);
      });
    });
  }
});

test.describe('the two narrow states (D-134)', () => {
  test.use({ viewport: NARROW });

  test('reading comes first and the code owns the viewport', async ({ page }) => {
    await gotoSession(page, sessionWith(FIXTURE_SESSION.exercises[1].payload.code, 1));

    // The reader arrives in the reading state; the answer controls are not
    // merely small, they are not on screen at all.
    await expect(page.locator('[data-pane="reading"]')).toHaveAttribute('data-active', 'true');
    await expect(page.locator('input[name="choice"]').first()).toBeHidden();
  });

  test('tapping a line carries spot_the_bug into answering with the line selected', async ({ page }) => {
    await gotoSession(page);

    await page.getByRole('button', { name: 'Select line 4', exact: true }).click();
    await expect(page.locator('[data-pane="answering"]')).toHaveAttribute('data-active', 'true');
    await expect(page.locator('input[name="reason"]').first()).toBeVisible();

    // ...and going back preserves it.
    await page.getByRole('button', { name: /Back to the code/ }).click();
    await expect(page.getByRole('button', { name: 'Select line 4', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });
});

test.describe('wrapped lines', () => {
  test.use({ viewport: NARROW });

  test('a long line wraps by default and tapping a continuation row selects it', async ({ page }) => {
    await gotoSession(page, sessionWith(`def checkout(basket):\n    ${LONG_LINE}\n    return result`));

    const line2 = page.getByRole('button', { name: 'Select line 2', exact: true });
    const line1 = page.getByRole('button', { name: 'Select line 1', exact: true });
    const box2 = (await line2.boundingBox())!;
    const box1 = (await line1.boundingBox())!;

    // Wrap is the default BELOW the breakpoint (D-130), with no preference set.
    expect(box2.height).toBeGreaterThan(box1.height * 1.5);

    // Tap the bottom of the wrapped block -- a continuation row.
    await page.mouse.click(box2.x + box2.width / 2, box2.y + box2.height - 4);

    // D-134: a line tap also carries you into the answering state, so come
    // back to the code before asserting which line is selected.
    await page.getByRole('button', { name: /Back to the code/ }).click();
    await expect(line2).toHaveAttribute('aria-pressed', 'true');
    await expect(line1).toHaveAttribute('aria-pressed', 'false');
    await expect(page.getByRole('button', { name: 'Select line 3', exact: true })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  test('the wrap preference persists and overrides the width default', async ({ page }) => {
    await gotoSession(page, sessionWith(`def checkout(basket):\n    ${LONG_LINE}\n    return result`));

    // Measure via the GUTTER BUTTON, which exists in both modes: the wrap
    // renderer and the scroll renderer are different trees, and [data-line]
    // only exists in the wrap one.
    const line2 = () => page.getByRole('button', { name: 'Select line 2', exact: true });
    const wrappedHeight = await line2().evaluate((el) => el.getBoundingClientRect().height);

    // D-132: the control lives in Profile now, not above the code. Setting it
    // there must change how the session renders -- that round trip through
    // storage is the whole contract.
    await page.goto('/profile');
    await page.getByRole('radio', { name: /Scroll/ }).check();

    await page.goto('/session');
    await expect(line2()).toBeVisible({ timeout: 15_000 });
    const scrolledHeight = await line2().evaluate((el) => el.getBoundingClientRect().height);

    // One row now, not several: the override beat the width default.
    expect(scrolledHeight).toBeLessThan(wrappedHeight);

    // And it survives a reload: a stored preference, not component state.
    await page.reload();
    await expect(line2()).toBeVisible({ timeout: 15_000 });
    const afterReload = await line2().evaluate((el) => el.getBoundingClientRect().height);
    expect(afterReload).toBeLessThan(wrappedHeight);
  });
});

test.describe('the sticky context header', () => {
  test.use({ viewport: NARROW });

  test('pins the enclosing signature once it scrolls out of view', async ({ page }) => {
    const body = Array.from({ length: 40 }, (_, i) => `    total += item_${i}.price`).join('\n');
    await gotoSession(page, sessionWith(`def compute_invoice_total(items):\n    total = 0\n${body}\n    return total`));

    // Nothing pinned at the top: the signature is its own first visible line.
    await expect(page.getByText('def compute_invoice_total(items):')).toBeVisible();

    const scroller = page.locator('[data-line="1"]').locator('xpath=ancestor::div[contains(@class,"overflow-y-auto")][1]');
    await scroller.evaluate((el) => el.scrollTo(0, 600));

    // Now that line 1 is above the fold, the header states what you are inside.
    const header = page.locator('.sticky').filter({ hasText: 'def compute_invoice_total(items):' });
    await expect(header).toBeVisible();
  });
});

test.describe('wrapped continuation indentation (D-132)', () => {
  test.use({ viewport: NARROW });

  test('a continuation row is indented PAST the code it continues, never before it', async ({ page }) => {
    // A deeply indented long line. The old hanging indent was relative to the
    // CONTAINER, so on a 12-space-indented line the continuation landed ~12
    // characters to the LEFT of the code -- reading as a statement at a
    // shallower nesting level. For a code-comprehension app that is worse than
    // horizontal scroll: scrolling hides structure, this misrepresents it.
    const deep =
      '            name = event["endpoint"] + "/" + str(event["status_code"]) + "?" + event["query"]';
    const code = ['def tally(events):', '    for event in events:', '        if event:', deep, '    return 1'].join('\n');
    await gotoSession(page, sessionWith(code));

    const geom = await page.evaluate(() => {
      const row = document.querySelector<HTMLElement>('[data-line="4"]');
      const span = row?.querySelector<HTMLElement>('span:nth-child(2)');
      if (!span) return null;
      // Group client rects by top: rects sharing a top are one VISUAL line.
      const range = document.createRange();
      range.selectNodeContents(span);
      const rects = Array.from(range.getClientRects()).filter((r) => r.width > 0.5 && r.height > 1);
      const byTop = new Map<number, number>();
      rects.forEach((r) => byTop.set(Math.round(r.top), Math.min(byTop.get(Math.round(r.top)) ?? Infinity, r.left)));
      const lines = Array.from(byTop.entries()).sort((a, b) => a[0] - b[0]);
      // Where the CODE starts on row 1 -- not the row's left edge, which is
      // where its leading whitespace starts.
      let codeLeft: number | null = null;
      const walker = document.createTreeWalker(span, NodeFilter.SHOW_TEXT);
      let node: Node | null;
      while ((node = walker.nextNode())) {
        const idx = (node.textContent ?? '').search(/\S/);
        if (idx === -1) continue;
        const r = document.createRange();
        r.setStart(node, idx);
        r.setEnd(node, idx + 1);
        codeLeft = r.getBoundingClientRect().left;
        break;
      }
      return { visualRows: lines.length, codeLeft, continuationLeft: lines.length > 1 ? lines[1][1] : null };
    });

    expect(geom, 'could not measure the wrapped line').not.toBeNull();
    expect(geom!.visualRows, 'the deep line must actually wrap').toBeGreaterThan(1);
    expect(geom!.continuationLeft!).toBeGreaterThan(geom!.codeLeft!);
  });

  test('the pane never renders a partial bottom row', async ({ page }) => {
    const long = Array.from({ length: 40 }, (_, i) => `    step_${i} = compute(${i})`).join('\n');
    await gotoSession(page, sessionWith(`def run():\n${long}\n    return step_0`));

    const partial = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll<HTMLElement>('[data-line]'));
      const scroller = rows[0].closest('.overflow-y-auto') as HTMLElement;
      const sr = scroller.getBoundingClientRect();
      return rows.filter((r) => {
        const b = r.getBoundingClientRect();
        const straddlesBottom = b.top < sr.bottom - 0.5 && b.bottom > sr.bottom + 0.5;
        return straddlesBottom;
      }).length;
    });
    expect(partial, 'a row is sliced by the pane edge').toBe(0);
  });
});

test.describe('reading density (D-132)', () => {
  test.use({ viewport: { width: 400, height: 844 } });

  test('only spot_the_bug while answering pays for tap-sized rows', async ({ page }) => {
    const long = Array.from({ length: 40 }, (_, i) => `    step_${i} = compute(${i})`).join('\n');
    const code = `def run():\n${long}\n    return step_0`;

    // trace answers in the sheet, so its lines are for reading only.
    await gotoSession(page, sessionWith(code, 1));
    const traceRow = await page.locator('[data-line="1"]').first().evaluate((el) => el.getBoundingClientRect().height);
    expect(traceRow, 'trace should read at the reading line-height').toBeLessThan(30);

    // spot_the_bug answers BY TAPPING A LINE, so its rows are targets.
    await gotoSession(page, sessionWith(code, 0));
    const stbRow = await page.locator('[data-line="1"]').first().evaluate((el) => el.getBoundingClientRect().height);
    expect(stbRow, 'spot_the_bug answering needs 44px rows').toBeGreaterThanOrEqual(44);

    // ...but its REVEAL is for reading, so the rows relax again.
    await page.getByRole('button', { name: 'Select line 4', exact: true }).click();
    await page.locator('input[name="reason"]').first().click();
    await page.getByRole('button', { name: 'Check answer' }).click();
    await expect(page.getByRole('button', { name: /Next|Finish/ })).toBeVisible({ timeout: 15_000 });
    const revealRow = await page.locator('[data-line="1"]').first().evaluate((el) => el.getBoundingClientRect().height);
    expect(revealRow, 'the reveal is for reading').toBeLessThan(30);
  });

  test('the reading state gives the code the whole viewport minus its action bar', async ({ page }) => {
    // The sheet this replaces rested at 118px -- 18% of a 667px viewport --
    // because its submit row was mounted while resting. The reading state's
    // only chrome is one action bar.
    // LONG content: with a 5-line snippet the pane correctly hugs its
    // content and the ratio measures the snippet, not the layout.
    const long = Array.from({ length: 40 }, (_, i) => `    step_${i} = compute(${i})`).join('\n');
    await gotoSession(page, sessionWith(`def run():\n${long}\n    return step_0`, 1));

    const chrome = await page.evaluate(() => {
      const pane = document.querySelector<HTMLElement>('[data-pane="reading"]');
      const scroller = pane?.querySelector<HTMLElement>('.overflow-y-auto');
      if (!pane || !scroller) return null;
      return {
        pane: pane.getBoundingClientRect().height,
        code: scroller.getBoundingClientRect().height,
      };
    });
    expect(chrome).not.toBeNull();
    // The code region is the majority of the reading state.
    expect(chrome!.code / chrome!.pane).toBeGreaterThan(0.6);
  });
});
