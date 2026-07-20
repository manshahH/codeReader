// Fixed payloads for the viewer visual-regression harness (D-129).
//
// Hermetic ON PURPOSE. The seeded specs get a randomly sampled session, so the
// three types (and which exercise represents each) vary run to run. That is
// fine for behaviour, useless for a before/after pixel comparison: a different
// snippet would read as a rendering difference when it is a content
// difference. These payloads are frozen, so any pixel that moves between the
// before and after runs moves because the refactor moved it.
//
// The code samples deliberately include a line long enough to overflow the
// 1280px viewport, because scroll-vs-wrap is exactly what decision 5 touches
// and the default (scroll) has to keep looking like it does today.

import type { Page } from '@playwright/test';

const USER = {
  id: '00000000-0000-0000-0000-0000000000aa',
  username: 'viewer-fixture',
  display_name: 'Viewer Fixture',
  avatar_url: null,
  level: 'mid',
  timezone: 'UTC',
  onboarded: true,
  email: null,
  email_verified: false,
  pending_email: null,
};

const STB_CODE = `def apply_discount(items, pct):
    total = 0
    for item in items:
        total += item.price
    discounted = total * (1 - pct)
    if discounted < 0:
        discounted = 0
    return round(discounted, 2)`;

const TRACE_CODE = `counts = {}
for word in ["a", "b", "a"]:
    counts[word] = counts.get(word, 0) + 1
result = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
print(result)`;

const PTF_CODE = `def merge_windows(windows):
    windows.sort(key=lambda w: w[0])
    merged = [windows[0]]
    for start, end in windows[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged`;

const PTF_TEST = `def test_merge_windows_handles_empty_input_without_raising_an_index_error():
    assert merge_windows([]) == []`;

export const FIXTURE_SESSION = {
  session_date: '2026-07-19',
  completed: false,
  exercises: [
    {
      slot: 1,
      exercise_id: '00000000-0000-0000-0000-000000000001',
      version: 1,
      type: 'spot_the_bug',
      concepts: ['arithmetic'],
      language: 'python',
      difficulty_band: 'easy',
      est_time_s: 60,
      is_boss: false,
      attempted: false,
      payload: {
        code: STB_CODE,
        // Real wire shape: the backend normalizes to `documents` at the
        // serialization boundary (D-129), so the fixtures carry documents too.
        // Legacy-shaped fixtures are what hid the predict_the_fix bug last time.
        documents: [{ id: 'primary', role: 'primary', code: STB_CODE, language: 'python' }],
        context_note: 'A checkout helper that applies a percentage discount to a basket.',
        answer_mode: 'line_and_reason',
        reason_options: [
          { id: 'r1', text: 'The discount percentage is applied as a multiplier instead of a subtraction.' },
          { id: 'r2', text: 'The quantity of each item is ignored, so the total undercounts multi-unit lines.' },
          { id: 'r3', text: 'Rounding happens before the clamp, so a negative total can survive.' },
        ],
      },
    },
    {
      slot: 2,
      exercise_id: '00000000-0000-0000-0000-000000000002',
      version: 1,
      type: 'trace',
      concepts: ['dicts'],
      language: 'python',
      difficulty_band: 'medium',
      est_time_s: 75,
      is_boss: false,
      attempted: false,
      payload: {
        code: TRACE_CODE,
        documents: [{ id: 'primary', role: 'primary', code: TRACE_CODE, language: 'python' }],
        context_note: 'A word-frequency count sorted by descending count, then alphabetically.',
        question: 'What does this print?',
        choices: [
          { id: 'c1', text: "[('a', 2), ('b', 1)]" },
          { id: 'c2', text: "[('b', 1), ('a', 2)]" },
          { id: 'c3', text: "[('a', 1), ('b', 1)]" },
        ],
      },
    },
    {
      slot: 3,
      exercise_id: '00000000-0000-0000-0000-000000000003',
      version: 1,
      type: 'predict_the_fix',
      concepts: ['edge-cases'],
      language: 'python',
      difficulty_band: 'hard',
      est_time_s: 90,
      is_boss: false,
      attempted: false,
      payload: {
        code: PTF_CODE,
        documents: [
          { id: 'primary', role: 'primary', code: PTF_CODE, language: 'python' },
          { id: 'failing_test', role: 'failing_test', code: PTF_TEST, language: 'python', label: 'Failing test' },
          { id: 'f1', role: 'choice', code: 'if not windows:\n    return []\nwindows.sort(key=lambda w: w[0])', language: 'python' },
          { id: 'f2', role: 'choice', code: 'merged = [windows[0]] if windows else []', language: 'python' },
          { id: 'f3', role: 'choice', code: 'windows = list(windows) or [(0, 0)]', language: 'python' },
        ],
        context_note: 'Merges overlapping time windows into the smallest covering set.',
        answer_mode: 'choice',
        question: 'Which fix makes the failing test pass?',
        failing_test: PTF_TEST,
        test_output: 'IndexError: list index out of range',
        choices: [
          { id: 'f1', text: 'if not windows:\n    return []\nwindows.sort(key=lambda w: w[0])' },
          { id: 'f2', text: 'merged = [windows[0]] if windows else []' },
          { id: 'f3', text: 'windows = list(windows) or [(0, 0)]' },
        ],
      },
    },
  ],
};

export const FIXTURE_REVEALS: Record<string, unknown> = {
  spot_the_bug: {
    correct_lines: [4],
    correct_reason_id: 'r2',
    explanation: {
      summary: 'The loop adds each item price once, ignoring how many units were ordered.',
      principle: 'When you aggregate over a collection, confirm what each element represents.',
      line_notes: [
        { line: 4, note: 'Adds price once per line item, not once per unit.' },
        { line: 5, note: 'Correct in isolation, but it is multiplying an already-wrong total.' },
      ],
    },
  },
  trace: {
    correct_choice_id: 'c1',
    explanation: {
      summary: 'Sorting by -count then key puts the twice-seen word first.',
      principle: 'A tuple sort key applies left to right, so the sign flips only the first term.',
      trace_table: [
        { line: 3, state: "counts = {'a': 1}" },
        { line: 3, state: "counts = {'a': 1, 'b': 1}" },
        { line: 3, state: "counts = {'a': 2, 'b': 1}" },
        { line: 4, state: "result = [('a', 2), ('b', 1)]" },
      ],
      why_wrong: [
        { choice_id: 'c2', note: 'That is ascending count order; the key negates the count.' },
        { choice_id: 'c3', note: "'a' is counted twice, so its value is 2, not 1." },
      ],
    },
  },
  predict_the_fix: {
    correct_choice_id: 'f1',
    explanation: {
      summary: 'Guarding the empty case before indexing is the only fix that returns [].',
      principle: 'Handle the empty collection at the boundary, not inside the loop.',
      why_wrong: [
        { choice_id: 'f2', note: 'Avoids the IndexError but still returns [] via a slower path that then re-enters the loop.' },
        { choice_id: 'f3', note: 'Invents a (0, 0) window that the caller never supplied.' },
      ],
    },
  },
};

// Which reveal answers which exercise. Keyed by exercise_id (which the attempt
// request carries) rather than by call order, so the stub stays correct however
// the harness walks the session.
const REVEAL_BY_EXERCISE_ID: Record<string, string> = {
  '00000000-0000-0000-0000-000000000001': 'spot_the_bug',
  '00000000-0000-0000-0000-000000000002': 'trace',
  '00000000-0000-0000-0000-000000000003': 'predict_the_fix',
};

/** Stub every route the session player touches, so the harness needs no
 * backend, no database, and no sampling. `session` overrides the default
 * fixture for tests that need a particular payload shape. */
export async function stubViewerRoutes(page: Page, opts: { session?: unknown } = {}): Promise<void> {
  const session = opts.session ?? FIXTURE_SESSION;
  const json = (body: unknown) => ({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });

  await page.route('**/v1/auth/refresh', (route) =>
    route.fulfill(json({ access_token: 'fixture-access-token', expires_in: 900, user: USER })),
  );
  await page.route('**/v1/me', (route) => route.fulfill(json({ user: USER })));
  await page.route('**/v1/session/today', (route) => route.fulfill(json(session)));
  await page.route('**/v1/attempts', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    const body = JSON.parse(route.request().postData() ?? '{}') as { exercise_id?: string };
    const revealFor = REVEAL_BY_EXERCISE_ID[body.exercise_id ?? ''] ?? 'spot_the_bug';
    await route.fulfill(
      json({
        attempt_id: 1,
        status: 'graded',
        is_correct: false,
        reveal: FIXTURE_REVEALS[revealFor],
        percentile: { solve_rate: 0.42, n: 120 },
        streak: null,
        session: { completed: false, remaining: 2, first_completed_session: false },
      }),
    );
  });
}

/**
 * Move the narrow layout into its ANSWERING state (D-134).
 *
 * Replaces raiseAnswerSheet: below the breakpoint the answer controls are a
 * full-screen state reached by an explicit toggle, not a sheet that rises over
 * the code. No-op above the breakpoint, where both live side by side.
 * Returns whether a switch happened.
 */
export async function enterAnsweringState(page: Page): Promise<boolean> {
  const reading = page.locator('[data-pane="reading"][data-active="true"]');
  if ((await reading.count()) === 0) return false;
  await reading
    .getByRole('button', { name: /Tap the buggy line|pick a reason|Answer|Review your answer/ })
    .first()
    .click();
  await page.locator('[data-pane="answering"][data-active="true"]').waitFor({ timeout: 5_000 });
  return true;
}
