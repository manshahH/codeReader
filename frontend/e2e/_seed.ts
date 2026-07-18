import { execFileSync } from 'node:child_process';
import path from 'node:path';

import type { BrowserContext } from '@playwright/test';

const API_BASE = process.env.E2E_API_BASE_URL ?? 'http://localhost:8000';

function repoRoot(): string {
  const cwd = process.cwd();
  return /[\\/]frontend$/.test(cwd) ? path.dirname(cwd) : cwd;
}

/**
 * Is the local stack (backend + its Postgres/Redis) actually up?
 *
 * The seeded specs need a real backend; the hermetic ones (which stub every
 * route) do not. When the stack is down these specs used to fail 15s later on
 * a UI selector -- "span.capitalize not found" -- which reads as a broken app
 * or a broken test, and sent this session on a real detour. It is neither: it
 * is a missing `docker compose up`. Specs call this and skip WITH A REASON
 * instead, so the output says what is actually wrong.
 *
 * Skipping, not failing, because a red suite that developers learn to ignore
 * stops being a signal. A named skip stays honest: it never claims the
 * ErrorBoundary regression was verified when it was not.
 */
export async function localStackIsUp(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/healthz`, {
      signal: AbortSignal.timeout(3000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export const STACK_REQUIRED =
  `needs the local stack: \`docker compose up -d\` (Postgres/Redis) plus the ` +
  `backend on ${API_BASE}. Hermetic specs run without it.`;

/**
 * Seed a fresh user + refresh token and set it as the `rt` cookie on the
 * context. seed_e2e.py mints the token the exact way the OAuth callback does,
 * and every call is a NEW user -- so each test that calls this gets its own
 * token. That is required because the token rotates the first time the SPA
 * refreshes, which is why a single shared E2E_REFRESH_TOKEN could never run two
 * real-backend specs in one invocation.
 */
export async function seedAuthCookie(context: BrowserContext): Promise<void> {
  let stdout: string;
  try {
    stdout = execFileSync('python', ['backend/scripts/seed_e2e.py'], {
      cwd: repoRoot(),
      env: { ...process.env, CODEREADER_ALLOW_SEED: '1' },
      encoding: 'utf8',
    });
  } catch (cause) {
    // The raw failure is a Python traceback ending in ConnectionRefusedError,
    // which is easy to misread as a test bug. Name the actual cause.
    throw new Error(`seed_e2e.py failed -- ${STACK_REQUIRED}`, { cause });
  }
  const line = stdout.trim().split('\n').filter(Boolean).pop() ?? '';
  const token = (JSON.parse(line) as { refresh_token: string }).refresh_token;
  const apiUrl = new URL(API_BASE);
  await context.addCookies([
    {
      name: 'rt',
      value: token,
      domain: apiUrl.hostname,
      path: '/',
      httpOnly: true,
      secure: false,
      sameSite: 'Lax',
    },
  ]);
}
