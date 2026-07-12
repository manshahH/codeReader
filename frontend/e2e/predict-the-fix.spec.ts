import { expect, test } from '@playwright/test';

// Deterministic per-type UI coverage for predict_the_fix, moved here from the
// live session smoke where requiring the sampler to serve a PTF was ~1-in-5
// flaky (FIX-B). Everything is stubbed, so this always exercises the PTF answer
// UI (choice radios of code diffs) and the PTF reveal, regardless of what the
// live pool would sample.

function stubUser() {
  return {
    id: 'u_test',
    username: 'tester',
    display_name: null,
    avatar_url: null,
    level: 'mid',
    timezone: 'UTC',
    onboarded: true,
  };
}

const PTF_EXERCISE = {
  slot: 1,
  exercise_id: 'ptf-1',
  version: 1,
  type: 'predict_the_fix',
  concepts: ['off-by-one'],
  language: 'python',
  difficulty_band: 'medium',
  est_time_s: 90,
  is_boss: false,
  attempted: false,
  payload: {
    code: 'def total(xs):\n    t = 0\n    for x in xs:\n        t = x\n    return t\n',
    context_note: 'Totals a list.',
    question: 'Which change makes the failing test pass?',
    failing_test: 'assert total([1, 2, 3]) == 6',
    test_output: 'AssertionError',
    answer_mode: 'choose_fix',
    choices: [
      { id: 'a', text: 'def total(xs):\n    t = 0\n    for x in xs:\n        t += x\n    return t\n' },
      { id: 'b', text: 'def total(xs):\n    t = 1\n    for x in xs:\n        t += x\n    return t\n' },
    ],
  },
};

test('predict_the_fix: answer UI and reveal render and grade', async ({ page }) => {
  await page.route('**/v1/auth/refresh', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'stub', expires_in: 900, user: stubUser() }),
    });
  });
  await page.route('**/v1/session/today', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ session_date: '2026-07-12', completed: false, exercises: [PTF_EXERCISE] }),
    }),
  );
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
      }),
    }),
  );
  await page.route('**/v1/attempts', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        attempt_id: 1,
        status: 'graded',
        is_correct: true,
        reveal: {
          correct_choice_id: 'a',
          explanation: {
            summary: 'Use += to accumulate.',
            principle: '= overwrites the running total.',
            why_wrong: [{ choice_id: 'b', note: 'Starting at 1 overcounts.' }],
          },
        },
        percentile: null,
        streak: null,
        session: { completed: true, remaining: 0, first_completed_session: false },
      }),
    });
  });

  await page.goto('/session');
  await expect(page.getByText('Your session is ready.')).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: 'Enter sandbox' }).click();

  // The PTF answer UI: code-diff choices as radios named "fix".
  await expect(page.getByText('Which change makes the failing test pass?')).toBeVisible();
  await page.locator('input[name="fix"]').first().click();
  await page.getByRole('button', { name: 'Check answer' }).click();

  // The PTF reveal renders the verdict and the winning fix.
  await expect(page.getByText(/^(Correct|Incorrect)\.$/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('The fix that passes the test')).toBeVisible();
});
