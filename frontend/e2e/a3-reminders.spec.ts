import { expect, test, type Page } from '@playwright/test';

/**
 * A3 reminders + recap UI (D-137), and its anti-slop audit.
 *
 * Hermetic: every route is stubbed, so this needs no backend and no seeded
 * content. It covers the three states docs/10 asks for (no verified email,
 * reminders off, reminders on) at desktop AND narrow, plus the docs/08
 * quality-floor audit run against COMPUTED STYLES rather than by eye -- the
 * slop catalogue's own method, and the same approach the milestone write-up
 * scores from.
 *
 * The audit PRINTS a report and asserts only the patterns that are objectively
 * wrong for this token system (a colored card edge, a gradient, an emoji in
 * UI). docs/08's "4+ patterns fails" is a judgement for the write-up, and a
 * test that failed on 3 and passed on 2 would be false precision.
 */

const NARROW = { width: 375, height: 667 };
const DESKTOP = { width: 1280, height: 800 };

type Prefs = { reminders_enabled: boolean; recap_enabled: boolean };

function stubUser(overrides: Record<string, unknown> = {}) {
  return {
    id: 'u_test',
    username: 'tester',
    display_name: null,
    avatar_url: null,
    level: 'mid',
    timezone: 'Europe/London',
    onboarded: true,
    email: 'dev@example.com',
    email_verified: true,
    pending_email: null,
    reminder_local_time: '08:00',
    email_prefs: { reminders_enabled: true, recap_enabled: true } satisfies Prefs,
    ...overrides,
  };
}

async function stubApp(page: Page, user: object) {
  await page.route('**/v1/auth/refresh', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'stub', expires_in: 900, user }),
    });
  });
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

const card = (page: Page) =>
  page.locator('section').filter({ hasText: 'Reminders and recap' });

// --------------------------------------------------------------------------
// The three states, at both widths
// --------------------------------------------------------------------------

for (const vp of [DESKTOP, NARROW]) {
  const label = `${vp.width}x${vp.height}`;

  test.describe(label, () => {
    test.use({ viewport: vp });

    test(`${label}: no verified address explains what unlocks reminders`, async ({ page }) => {
      await stubApp(page, stubUser({ email: null, email_verified: false }));
      await page.goto('/profile');

      const panel = card(page);
      await expect(panel).toContainText('confirm an email address');
      // No controls are offered, because none of them could do anything.
      await expect(panel.locator('input[type="checkbox"]')).toHaveCount(0);
      await expect(panel.locator('input[type="time"]')).toHaveCount(0);
    });

    test(`${label}: reminders on shows the time and the timezone it means`, async ({ page }) => {
      await stubApp(page, stubUser());
      await page.goto('/profile');

      const panel = card(page);
      await expect(panel.locator('input[type="time"]')).toHaveValue('08:00');
      // The time is meaningless without saying whose clock it is.
      await expect(panel).toContainText('Europe/London');
      await expect(panel.locator('input[type="checkbox"]')).toHaveCount(2);
    });

    test(`${label}: reminders off hides the schedule but keeps the recap`, async ({ page }) => {
      await stubApp(
        page,
        stubUser({ email_prefs: { reminders_enabled: false, recap_enabled: true } }),
      );
      await page.goto('/profile');

      const panel = card(page);
      // Consent off means the schedule is not a question worth asking.
      await expect(panel.locator('input[type="time"]')).toHaveCount(0);
      // But the recap is a SEPARATE consent and must still be there.
      await expect(panel).toContainText('Weekly recap');
      await expect(panel.locator('input[type="checkbox"]')).toHaveCount(2);
    });

    test(`${label}: consented with no time set reads as on, not off`, async ({ page }) => {
      await stubApp(page, stubUser({ reminder_local_time: null }));
      await page.goto('/profile');

      const panel = card(page);
      // The D-137(6) three-way state: this must NOT render as "off".
      await expect(panel).toContainText('no time set yet');
      await expect(panel.locator('input[type="time"]')).toHaveValue('');
    });
  });
}

// --------------------------------------------------------------------------
// Narrow usability: the card must be usable on a phone, not merely present
// --------------------------------------------------------------------------

test.describe('narrow usability', () => {
  test.use({ viewport: NARROW });

  test('the reminders card causes no horizontal overflow', async ({ page }) => {
    await stubApp(page, stubUser());
    await page.goto('/profile');
    await expect(card(page)).toBeVisible();

    const overflowing = await page.evaluate(() => {
      const vw = document.documentElement.clientWidth;
      return Array.from(document.querySelectorAll('body *'))
        .filter((el) => el.getBoundingClientRect().right > vw + 1)
        .map((el) => `${el.tagName}.${(el.className || '').toString().slice(0, 40)}`);
    });

    expect(overflowing).toEqual([]);
  });

  test('every control in the card clears the 44px touch floor', async ({ page }) => {
    await stubApp(page, stubUser());
    await page.goto('/profile');

    const small = await card(page).evaluate((root) => {
      // TAP TARGETS ONLY. A bare <label for="..."> is a caption, not a target:
      // it is inline prose sized by its line box, and padding it to 44px would
      // put a large invisible hit area around a word. The toggle rows DO
      // contain their input, so they are targets and are included.
      const controls = root.querySelectorAll(
        'button, input[type="time"], label:has(input)',
      );
      return Array.from(controls)
        .map((el) => ({ tag: el.tagName, h: Math.round(el.getBoundingClientRect().height) }))
        .filter((c) => c.h > 0 && c.h < 44);
    });

    expect(small, `controls under the 44px touch floor: ${JSON.stringify(small)}`).toEqual([]);
  });
});

// --------------------------------------------------------------------------
// The public unsubscribe page
// --------------------------------------------------------------------------

test('unsubscribe: previewing does not unsubscribe, pressing does', async ({ page }) => {
  let posted = 0;
  await page.route('**/v1/unsubscribe/preview**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ kind: 'reminder' }),
    }),
  );
  await page.route('**/v1/unsubscribe?**', (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    posted += 1;
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ unsubscribed: 'reminder' }),
    });
  });

  await page.goto('/unsubscribe?token=stub.token');

  await expect(page.getByText('Turn off daily reminders?')).toBeVisible();
  // Merely landing on the page must not act: a link scanner following the URL
  // would otherwise unsubscribe someone who never clicked (D-137(7)).
  expect(posted).toBe(0);

  await page.getByRole('button', { name: /turn off daily reminders/i }).click();

  await expect(page.getByText(/we will not send/i)).toBeVisible();
  expect(posted).toBe(1);
});

test('unsubscribe: works with no session at all', async ({ page, context }) => {
  await context.clearCookies();
  // Auth refresh fails, exactly as it would for a signed-out reader arriving
  // from their inbox. The page must still work.
  await page.route('**/v1/auth/refresh', (route) =>
    route.fulfill({ status: 401, contentType: 'application/json', body: '{}' }),
  );
  await page.route('**/v1/unsubscribe/preview**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ kind: 'recap' }),
    }),
  );

  await page.goto('/unsubscribe?token=stub.token');

  await expect(page.getByText('Turn off the weekly recap?')).toBeVisible();
});

// --------------------------------------------------------------------------
// The anti-slop audit (docs/08 quality floor, computed styles)
// --------------------------------------------------------------------------

test('anti-slop audit: the reminders card and the unsubscribe page', async ({ page }) => {
  const surfaces = [
    { name: 'profile reminders card 1280x800', path: '/profile', ...DESKTOP },
    { name: 'profile reminders card 375x667', path: '/profile', ...NARROW },
    { name: 'unsubscribe 375x667', path: '/unsubscribe?token=stub.token', ...NARROW },
  ];

  await page.route('**/v1/unsubscribe/preview**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ kind: 'reminder' }),
    }),
  );
  await stubApp(page, stubUser());

  const report: Record<string, unknown>[] = [];

  for (const surface of surfaces) {
    await page.setViewportSize({ width: surface.width, height: surface.height });
    await page.goto(surface.path);
    await page.waitForTimeout(250);

    const measured = await page.evaluate(() => {
      const parseRgb = (v: string) => {
        const m = v.match(/rgba?\(([^)]+)\)/);
        if (!m) return null;
        const p = m[1].split(',').map((n) => parseFloat(n.trim()));
        return p.length >= 3 ? [p[0], p[1], p[2]] : null;
      };
      // Lavender-indigo band: blue dominant, red close behind, green lowest.
      const isVibePurple = (v: string) => {
        const rgb = parseRgb(v);
        if (!rgb) return false;
        const [r, g, b] = rgb;
        return b > 120 && b - g > 40 && r > g && b - r < 90 && r - g > 10;
      };

      const fonts = new Set<string>();
      const radii = new Set<string>();
      let gradientCount = 0;
      let colouredShadows = 0;
      let purpleCount = 0;
      let upperLabels = 0;
      const colouredEdgeBorders: string[] = [];
      let emojiInUi = 0;

      const all = Array.from(document.querySelectorAll('body *'));
      for (const el of all) {
        const cs = getComputedStyle(el);
        fonts.add(cs.fontFamily.split(',')[0].replace(/["']/g, '').trim());
        if (parseFloat(cs.borderTopLeftRadius) > 0) radii.add(cs.borderTopLeftRadius);
        if (cs.backgroundImage.includes('gradient')) gradientCount += 1;
        if (cs.textTransform === 'uppercase') upperLabels += 1;
        if (isVibePurple(cs.color) || isVibePurple(cs.backgroundColor)) purpleCount += 1;
        if (cs.boxShadow && cs.boxShadow !== 'none') {
          const rgb = parseRgb(cs.boxShadow);
          if (rgb && !(rgb[0] === rgb[1] && rgb[1] === rgb[2])) colouredShadows += 1;
        }
        // Colored left/top edge border: the single most specific tell.
        const edges: [string, string, string][] = [
          ['left', cs.borderLeftWidth, cs.borderLeftColor],
          ['top', cs.borderTopWidth, cs.borderTopColor],
        ];
        for (const [side, width, color] of edges) {
          const w = parseFloat(width);
          if (w < 2 || w > 6) continue;
          const others =
            side === 'left'
              ? [cs.borderRightWidth, cs.borderTopWidth, cs.borderBottomWidth]
              : [cs.borderBottomWidth, cs.borderLeftWidth, cs.borderRightWidth];
          if (others.every((o) => parseFloat(o) === 0)) colouredEdgeBorders.push(`${side} ${color}`);
        }
      }

      const emojiRe = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
      for (const el of Array.from(document.querySelectorAll('nav *, button, a, label, p, span'))) {
        const own = Array.from(el.childNodes)
          .filter((n) => n.nodeType === 3)
          .map((n) => n.textContent ?? '')
          .join('');
        if (emojiRe.test(own)) emojiInUi += 1;
      }

      return {
        fonts: Array.from(fonts),
        radii: Array.from(radii),
        gradientCount,
        colouredShadows,
        purpleCount,
        upperLabels,
        colouredEdgeBorders,
        emojiInUi,
      };
    });

    report.push({ surface: surface.name, ...measured });

    // The three that are objectively wrong for this token system are asserted;
    // the rest are reported for the write-up.
    expect(measured.colouredEdgeBorders, `${surface.name}: colored card edge`).toEqual([]);
    expect(measured.gradientCount, `${surface.name}: gradients`).toBe(0);
    expect(measured.emojiInUi, `${surface.name}: emoji used as UI`).toBe(0);
    expect(measured.purpleCount, `${surface.name}: vibe-purple`).toBe(0);
  }

  console.log('\nANTI-SLOP AUDIT (A3 surfaces)\n' + JSON.stringify(report, null, 2));
});
