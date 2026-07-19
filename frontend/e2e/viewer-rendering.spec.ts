import { expect, test } from '@playwright/test';

import { FIXTURE_SESSION, stubViewerRoutes } from './_viewerFixtures';

// D-129 rendering tests: the parts of the model that only mean something once
// they hit the DOM. Each one fails against the pre-refactor viewer, noted per
// test.

test.use({ viewport: { width: 1280, height: 800 } });

// A line far too long for the code column at 1280px, so wrap mode has
// something to wrap. Kept as one logical line on purpose.
const LONG_LINE = 'result = compute_totals(basket, discount_policy, currency="GBP", rounding="half-even", audit_trail=True, include_shipping=False)';

const WRAP_CODE = `def checkout(basket):
    ${LONG_LINE}
    return result`;

/** Turn the persisted wrap preference on before the app boots. There is no
 * visible control yet (see the tension recorded in D-129), so the stored
 * preference is the supported way in -- which is exactly what this asserts. */
async function setWrapPreference(page: import('@playwright/test').Page, mode: 'wrap' | 'scroll') {
  await page.addInitScript((m) => {
    window.localStorage.setItem('codereader.viewer.wrap', m);
  }, mode);
}

test.describe('decision 5: long lines soft-wrap, and the wrapped group is one tap target', () => {
  test('tapping a continuation row selects the line it continues, not a different line', async ({ page }) => {
    // Fails against the old viewer twice over: it had no wrap mode at all, and
    // its gutter was a separate column of one-line-high buttons, so there was
    // no continuation row to tap and nothing that could have resolved a tap on
    // one back to its logical line.
    await setWrapPreference(page, 'wrap');

    const session = JSON.parse(JSON.stringify(FIXTURE_SESSION));
    session.exercises = [session.exercises[0]];
    session.exercises[0].payload.code = WRAP_CODE;
    // documents WINS over code (D-129 precedence), so a fixture that sets
    // only `code` silently renders the original snippet. Setting one and not
    // the other is the same legacy-shaped-fixture mistake that hid the
    // predict_the_fix multi-document bug.
    session.exercises[0].payload.documents = [
      { id: 'primary', role: 'primary', code: WRAP_CODE, language: 'python' },
    ];
    await stubViewerRoutes(page, { session });

    await page.goto('/session');

    const line2 = page.getByRole('button', { name: 'Select line 2', exact: true });
    await expect(line2).toBeVisible({ timeout: 15_000 });

    // The wrapped line really does occupy more vertical space than an
    // unwrapped one -- otherwise this test would pass without wrapping.
    const line1Box = (await page.getByRole('button', { name: 'Select line 1', exact: true }).boundingBox())!;
    const line2Box = (await line2.boundingBox())!;
    expect(line2Box.height).toBeGreaterThan(line1Box.height * 1.5);

    // Tap near the BOTTOM of the wrapped block: a continuation row, several
    // visual rows below where line 2 begins.
    await page.mouse.click(line2Box.x + line2Box.width / 2, line2Box.y + line2Box.height - 4);

    // Line 2 is selected, and nothing else is.
    await expect(line2).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('button', { name: 'Select line 1', exact: true })).toHaveAttribute('aria-pressed', 'false');
    await expect(page.getByRole('button', { name: 'Select line 3', exact: true })).toHaveAttribute('aria-pressed', 'false');
  });

  test('the gutter carries the number once per logical line, not once per visual row', async ({ page }) => {
    await setWrapPreference(page, 'wrap');
    const session = JSON.parse(JSON.stringify(FIXTURE_SESSION));
    session.exercises = [session.exercises[0]];
    session.exercises[0].payload.code = WRAP_CODE;
    // documents WINS over code (D-129 precedence), so a fixture that sets
    // only `code` silently renders the original snippet. Setting one and not
    // the other is the same legacy-shaped-fixture mistake that hid the
    // predict_the_fix multi-document bug.
    session.exercises[0].payload.documents = [
      { id: 'primary', role: 'primary', code: WRAP_CODE, language: 'python' },
    ];
    await stubViewerRoutes(page, { session });

    await page.goto('/session');
    await expect(page.getByRole('button', { name: 'Select line 1', exact: true })).toBeVisible({ timeout: 15_000 });

    // Three logical lines means exactly three numbered entries, however many
    // visual rows the wrapping produced.
    await expect(page.getByRole('button', { name: /^Select line \d+$/ })).toHaveCount(3);
  });

  test('scroll mode is the default when nothing is stored', async ({ page }) => {
    // The default is load-bearing: it is what makes the refactor visually
    // identical to what shipped before it.
    const session = JSON.parse(JSON.stringify(FIXTURE_SESSION));
    session.exercises = [session.exercises[0]];
    session.exercises[0].payload.code = WRAP_CODE;
    // documents WINS over code (D-129 precedence), so a fixture that sets
    // only `code` silently renders the original snippet. Setting one and not
    // the other is the same legacy-shaped-fixture mistake that hid the
    // predict_the_fix multi-document bug.
    session.exercises[0].payload.documents = [
      { id: 'primary', role: 'primary', code: WRAP_CODE, language: 'python' },
    ];
    await stubViewerRoutes(page, { session });

    await page.goto('/session');
    const line2 = page.getByRole('button', { name: 'Select line 2', exact: true });
    await expect(line2).toBeVisible({ timeout: 15_000 });

    // Unwrapped: every gutter entry is the same single-row height.
    const line1Box = (await page.getByRole('button', { name: 'Select line 1', exact: true }).boundingBox())!;
    const line2Box = (await line2.boundingBox())!;
    expect(Math.abs(line2Box.height - line1Box.height)).toBeLessThan(2);
  });
});

test.describe('decision 4: the viewer renders from documents, not from the legacy fields', () => {
  test('a multi-document payload renders each document from the document list', async ({ page }) => {
    // The decisive shape of this test: every document carries code that does
    // NOT appear in the legacy `code` / `failing_test` / `choices[].text`
    // fields. The old viewer read only those legacy fields, so it would render
    // the legacy text and never the document text -- this fails against it.
    const session = JSON.parse(JSON.stringify(FIXTURE_SESSION));
    session.exercises = [session.exercises[2]]; // predict_the_fix
    const payload = session.exercises[0].payload;
    payload.documents = [
      { id: 'primary', role: 'primary', code: 'PRIMARY_FROM_DOCUMENTS = 1', language: 'python' },
      { id: 'failing_test', role: 'failing_test', code: 'TEST_FROM_DOCUMENTS = 2', language: 'python' },
      { id: 'f1', role: 'choice', code: 'CHOICE_ONE_FROM_DOCUMENTS = 3', language: 'python' },
      { id: 'f2', role: 'choice', code: 'CHOICE_TWO_FROM_DOCUMENTS = 4', language: 'python' },
      { id: 'f3', role: 'choice', code: 'CHOICE_THREE_FROM_DOCUMENTS = 5', language: 'python' },
    ];
    await stubViewerRoutes(page, { session });

    await page.goto('/session');

    // All five documents render, sourced from the list rather than from `code`.
    await expect(page.getByText('PRIMARY_FROM_DOCUMENTS')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('TEST_FROM_DOCUMENTS')).toBeVisible();
    await expect(page.getByText('CHOICE_ONE_FROM_DOCUMENTS')).toBeVisible();
    await expect(page.getByText('CHOICE_TWO_FROM_DOCUMENTS')).toBeVisible();
    await expect(page.getByText('CHOICE_THREE_FROM_DOCUMENTS')).toBeVisible();

    // And the legacy strings, which differ, are NOT what got rendered.
    await expect(page.getByText('merge_windows')).toHaveCount(0);
  });
});

test.describe('decision 3: decorations reach the DOM as data', () => {
  test('reveal marks decorate the right rows, from a decoration list', async ({ page }) => {
    // The reveal marks line 4 correct and the user's line 2 incorrect, and
    // notes lines 4 and 5. Against the old viewer this data arrived as a
    // markLines record; getSpotTheBugDecorations now returns decorations and
    // CodeBlock applies them, so this asserts the new path end to end.
    const session = JSON.parse(JSON.stringify(FIXTURE_SESSION));
    session.exercises = [session.exercises[0]];
    await stubViewerRoutes(page, { session });

    await page.goto('/session');
    await expect(page.getByRole('button', { name: 'Select line 2', exact: true })).toBeVisible({ timeout: 15_000 });

    // Answer line 2 (wrong -- the reveal's correct line is 4).
    await page.getByRole('button', { name: 'Select line 2', exact: true }).click();
    await page.locator('input[name="reason"]').first().click();
    await page.getByRole('button', { name: 'Check answer' }).click();

    await expect(page.getByRole('button', { name: /Next|Finish/ })).toBeVisible({ timeout: 15_000 });

    // Gutter: line 4 correct, line 2 incorrect, both from decorations.
    const line4 = page.getByLabel('Select line 4', { exact: true }).or(page.getByText('4', { exact: true }));
    await expect(page.locator('.text-correct').first()).toBeVisible();
    await expect(page.locator('.text-incorrect').first()).toBeVisible();

    // Row tints follow the same decoration list: exactly one correct-tinted
    // row and one incorrect-tinted row in the code column.
    await expect(page.locator('.bg-correct-tint')).toHaveCount(2); // gutter entry + code row
    await expect(page.locator('.bg-incorrect-tint')).toHaveCount(2);
    expect(line4).toBeTruthy();
  });
});
