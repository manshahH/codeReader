import { test } from '@playwright/test';

import { stubViewerRoutes } from './_viewerFixtures';

// The docs/08 quality-floor audit, run against COMPUTED STYLES rather than by
// eye -- the slop catalogue's own method (Krebs scored 1,590 pages with
// Playwright and no LLM judge, deliberately, to avoid measuring the bias with
// the bias). docs/08: a screen triggering 4+ catalogue patterns fails.
//
// This prints a report; it does not assert. The score is a judgement that
// belongs in the milestone write-up, and a test that fails on "3 patterns" and
// passes on "2" would be false precision.

const SCREENS = [
  { name: 'session 1280x800', width: 1280, height: 800, path: '/session' },
  { name: 'session 375x667', width: 375, height: 667, path: '/session' },
];

test('slop catalogue audit', async ({ page }) => {
  for (const screen of SCREENS) {
    await page.setViewportSize({ width: screen.width, height: screen.height });
    await stubViewerRoutes(page);
    await page.goto(screen.path);
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => document.fonts.ready);

    const report = await page.evaluate(() => {
      const all = Array.from(document.querySelectorAll<HTMLElement>('body *'));
      const styles = all.map((el) => ({ el, cs: getComputedStyle(el) }));

      const parseRgb = (value: string): [number, number, number] | null => {
        const m = /rgba?\(([^)]+)\)/.exec(value);
        if (!m) return null;
        const [r, g, b] = m[1].split(',').map((n) => parseFloat(n));
        return [r, g, b];
      };
      // Lavender-indigo band: blue dominant, red close behind, green lowest.
      const isVibePurple = (value: string) => {
        const rgb = parseRgb(value);
        if (!rgb) return false;
        const [r, g, b] = rgb;
        return b > 120 && b - g > 40 && r > g && b - r < 90 && r - g > 10;
      };

      const fonts = new Set<string>();
      const radii = new Set<string>();
      const gradients: string[] = [];
      const colouredShadows: string[] = [];
      const purples: string[] = [];
      const upperLabels: string[] = [];
      const colouredEdgeBorders: string[] = [];

      styles.forEach(({ el, cs }) => {
        if (el.textContent && el.textContent.trim()) fonts.add(cs.fontFamily.split(',')[0].replace(/["']/g, ''));
        if (cs.borderRadius && cs.borderRadius !== '0px') radii.add(cs.borderRadius);
        if (cs.backgroundImage && cs.backgroundImage.includes('gradient')) gradients.push(cs.backgroundImage.slice(0, 60));
        if (cs.boxShadow && cs.boxShadow !== 'none') {
          const rgb = parseRgb(cs.boxShadow);
          // A shadow is "coloured" when it is not a neutral/near-black.
          if (rgb && !(Math.abs(rgb[0] - rgb[1]) < 12 && Math.abs(rgb[1] - rgb[2]) < 12)) {
            colouredShadows.push(cs.boxShadow.slice(0, 60));
          }
        }
        if (isVibePurple(cs.color) || isVibePurple(cs.backgroundColor)) {
          purples.push(`${el.tagName}.${el.className?.toString().slice(0, 40)}`);
        }
        if (cs.textTransform === 'uppercase' && (el.textContent ?? '').trim().length > 1) {
          upperLabels.push((el.textContent ?? '').trim().slice(0, 30));
        }
        // Colored left/top edge border: the single most specific tell.
        const edges = [
          ['left', cs.borderLeftWidth, cs.borderLeftColor],
          ['top', cs.borderTopWidth, cs.borderTopColor],
        ] as const;
        edges.forEach(([side, width, color]) => {
          const w = parseFloat(width);
          if (w < 2 || w > 6) return;
          const others = side === 'left'
            ? [cs.borderRightWidth, cs.borderTopWidth, cs.borderBottomWidth]
            : [cs.borderBottomWidth, cs.borderLeftWidth, cs.borderRightWidth];
          if (others.every((o) => parseFloat(o) === 0)) colouredEdgeBorders.push(`${side} ${color}`);
        });
      });

      // Body-text contrast against the reading surface.
      const contrast = (fg: string, bg: string) => {
        const lum = (c: string) => {
          const rgb = parseRgb(c);
          if (!rgb) return null;
          const [r, g, b] = rgb.map((v) => {
            const s = v / 255;
            return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
          });
          return 0.2126 * r + 0.7152 * g + 0.0722 * b;
        };
        const l1 = lum(fg);
        const l2 = lum(bg);
        if (l1 === null || l2 === null) return null;
        const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
        return (hi + 0.05) / (lo + 0.05);
      };
      const bodyBg = getComputedStyle(document.body).backgroundColor;
      const proseContrasts: { text: string; ratio: number }[] = [];
      Array.from(document.querySelectorAll<HTMLElement>('p, li, label, span')).forEach((el) => {
        const text = (el.textContent ?? '').trim();
        if (text.length < 12) return;
        const cs = getComputedStyle(el);
        let bg = cs.backgroundColor;
        if (bg === 'rgba(0, 0, 0, 0)') bg = bodyBg;
        const ratio = contrast(cs.color, bg);
        if (ratio !== null) proseContrasts.push({ text: text.slice(0, 30), ratio: Math.round(ratio * 100) / 100 });
      });

      const emojiInUi = Array.from(document.querySelectorAll<HTMLElement>('nav *, header *, button, a'))
        .map((el) => (el.textContent ?? '').trim())
        .filter((t) => /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(t));

      return {
        fonts: Array.from(fonts),
        radii: Array.from(radii),
        gradientCount: gradients.length,
        colouredShadows: Array.from(new Set(colouredShadows)),
        purpleCount: purples.length,
        upperLabels: Array.from(new Set(upperLabels)),
        colouredEdgeBorders: Array.from(new Set(colouredEdgeBorders)),
        worstProseContrast: proseContrasts.sort((a, b) => a.ratio - b.ratio).slice(0, 4),
        emojiInUi,
      };
    });

    console.log(`\n===== SLOP AUDIT: ${screen.name} =====`);
    console.log(JSON.stringify(report, null, 2));
  }
});
