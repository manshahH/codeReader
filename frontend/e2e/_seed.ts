import { execFileSync } from 'node:child_process';
import path from 'node:path';

import type { BrowserContext } from '@playwright/test';

const API_BASE = process.env.E2E_API_BASE_URL ?? 'http://localhost:8000';

function repoRoot(): string {
  const cwd = process.cwd();
  return /[\\/]frontend$/.test(cwd) ? path.dirname(cwd) : cwd;
}

/**
 * Seed a fresh user + refresh token and set it as the `rt` cookie on the
 * context. seed_e2e.py mints the token the exact way the OAuth callback does,
 * and every call is a NEW user -- so each test that calls this gets its own
 * token. That is required because the token rotates the first time the SPA
 * refreshes, which is why a single shared E2E_REFRESH_TOKEN could never run two
 * real-backend specs in one invocation.
 */
export async function seedAuthCookie(context: BrowserContext): Promise<void> {
  const stdout = execFileSync('python', ['backend/scripts/seed_e2e.py'], {
    cwd: repoRoot(),
    env: { ...process.env, CODEREADER_ALLOW_SEED: '1' },
    encoding: 'utf8',
  });
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
