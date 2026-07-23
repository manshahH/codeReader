import { defineConfig, devices } from '@playwright/test';

import { D136_TAG, d136Retries } from './e2e/_d136';

// When E2E_BASE_URL is set, we are deliberately pointing the suite at something
// that already exists (a deployed preview, a hand-started dev server) and
// Playwright must not start or manage a server. Otherwise it owns the server
// itself -- see the webServer note below for why that matters.
const externalBase = process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: externalBase ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  // D-136: the flaky continuation-row specs (tagged @d136-flaky) run in their
  // own project WITH retries, so a flake is tolerated but a consistent failure
  // is still red. EVERY other spec runs in `chromium` with retries 0 (the
  // top-level default above), so a genuinely new regression is never masked.
  // The tolerance is temporary and expires; see e2e/_d136.ts.
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      grepInvert: new RegExp(D136_TAG),
    },
    {
      name: 'd136-tolerated',
      use: { ...devices['Desktop Chrome'] },
      grep: new RegExp(D136_TAG),
      retries: d136Retries(),
    },
  ],

  // Playwright starts and owns its own dev server.
  //
  // This config previously had no webServer block, so it silently trusted
  // whatever happened to be listening on :5173. That cost a real debugging
  // detour during A1: a LONG-RUNNING dev server was serving a stale
  // Dashboard.tsx with zero occurrences of the component under test, and the
  // specs failed as though the feature were broken. Testing stale bytes is
  // worse than not testing, because it produces confident wrong answers.
  //
  // reuseExistingServer is FALSE, which is the whole fix: a server Playwright
  // just started cannot be serving yesterday's modules. Staleness came from the
  // server's AGE, not from dev mode, so a fresh `vite` is sufficient and a
  // production build is not required to get freshness.
  //
  // It must be the DEV server, not `vite preview`. There is no vite proxy in
  // this repo: dev resolves VITE_API_BASE_URL to http://localhost:8000, while
  // .env.production sets it to '' because production is same-origin behind the
  // vercel.json rewrite (D-114). A preview build therefore has no backend to
  // talk to locally, and every seeded spec (session, predict-the-fix,
  // reveal-error-boundary) lands on the login screen.
  //
  // server.strictPort is set in vite.config.ts so a busy 5173 is a loud
  // failure. Without it vite quietly falls back to 5174 while this url check
  // succeeds against the OLD server on 5173 -- reintroducing the exact bug.
  ...(externalBase
    ? {}
    : {
        webServer: {
          command: 'npm run dev',
          url: 'http://localhost:5173',
          reuseExistingServer: false,
          timeout: 120_000,
          stdout: 'pipe',
          stderr: 'pipe',
        },
      }),
});
