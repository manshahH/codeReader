// Access token lives in memory only (this module's closure) -- never
// localStorage/sessionStorage. The refresh token is the backend-set
// HttpOnly cookie; this client never reads or stores it.
import type {
  AccuracyHistoryDay,
  ActivityDay,
  AttemptRequest,
  AttemptResponse,
  ConceptMastery,
  DisputeRequest,
  DisputeResponse,
  Level,
  MeSessionSummary,
  MeStats,
  RefreshResponse,
  ReviewRequest,
  ReviewResponse,
  ReviewStatusResponse,
  SessionResponse,
  SessionReviewResponse,
  StreakRepairResponse,
  User,
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

let accessToken: string | null = null;
let refreshInFlight: Promise<RefreshResponse> | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function clearAccessToken(): void {
  accessToken = null;
}

export class ApiError extends Error {
  code: string;
  requestId: string | undefined;
  status: number;
  retryAfterSeconds: number | undefined;

  constructor(status: number, code: string, message: string, requestId?: string, retryAfterSeconds?: number) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

function retryAfter(response: Response): number | undefined {
  const header = response.headers.get('Retry-After');
  return header ? Number(header) : undefined;
}

async function parseErrorBody(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { error?: { code: string; message: string; request_id: string } };
    if (body.error) {
      return new ApiError(response.status, body.error.code, body.error.message, body.error.request_id, retryAfter(response));
    }
  } catch {
    // fall through to generic error below
  }
  return new ApiError(response.status, 'internal', 'Something went wrong.', undefined, retryAfter(response));
}

export async function refresh(): Promise<RefreshResponse> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    const response = await fetch(`${API_BASE}/v1/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!response.ok) {
      accessToken = null;
      throw await parseErrorBody(response);
    }
    const body = (await response.json()) as RefreshResponse;
    accessToken = body.access_token;
    return body;
  })();
  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/v1/auth/logout`, { method: 'POST', credentials: 'include' });
  accessToken = null;
}

export function githubLoginUrl(): string {
  return `${API_BASE}/v1/auth/github/start`;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  skipAuth?: boolean;
}

interface RawResult<T> {
  json: T;
  response: Response;
}

async function requestRaw<T>(path: string, options: RequestOptions = {}, isRetry = false): Promise<RawResult<T>> {
  const headers: Record<string, string> = { ...options.headers };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (!options.skipAuth && accessToken) headers.Authorization = `Bearer ${accessToken}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? 'GET',
      headers,
      credentials: 'include',
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'network_error', 'Could not reach the server. Check your connection.');
  }

  if (response.status === 401 && !options.skipAuth && !isRetry) {
    try {
      await refresh();
    } catch {
      throw await parseErrorBody(response);
    }
    return requestRaw<T>(path, options, true);
  }

  if (!response.ok) throw await parseErrorBody(response);
  if (response.status === 204) return { json: undefined as T, response };

  const json = (await response.json()) as T;
  // Idempotent-replay flag is exposed for callers that care (session player
  // logs it, never surfaces it as an error).
  if (response.headers.get('X-Idempotent-Replay') === 'true' && typeof json === 'object' && json !== null) {
    Object.defineProperty(json as object, '__idempotentReplay', { value: true, enumerable: false });
  }
  return { json, response };
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { json } = await requestRaw<T>(path, options);
  return json;
}

export function getSessionToday(): Promise<SessionResponse> {
  return request<SessionResponse>('/v1/session/today');
}

export function postAttempt(idempotencyKey: string, body: AttemptRequest): Promise<AttemptResponse> {
  return request<AttemptResponse>('/v1/attempts', {
    method: 'POST',
    body,
    headers: { 'Idempotency-Key': idempotencyKey },
  });
}

export function repairStreak(idempotencyKey: string): Promise<StreakRepairResponse> {
  return request<StreakRepairResponse>('/v1/streak/repair', {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
  });
}

export function getAttempt(attemptId: number): Promise<AttemptResponse> {
  return request<AttemptResponse>(`/v1/attempts/${attemptId}`);
}

/** Polling needs the `Retry-After` hint (docs/05 section 5), which the plain
 * `request()` helper doesn't surface. */
export async function getAttemptPoll(attemptId: number): Promise<{ body: AttemptResponse; retryAfterSeconds: number | null }> {
  const { json, response } = await requestRaw<AttemptResponse>(`/v1/attempts/${attemptId}`);
  const header = response.headers.get('Retry-After');
  return { body: json, retryAfterSeconds: header ? Number(header) : null };
}

export function getMe(): Promise<{ user: User }> {
  return request<{ user: User }>('/v1/me');
}

export function patchMe(body: Partial<{ display_name: string; timezone: string; level: Level; reminder_local_time: string | null }>): Promise<{ user: User } & Record<string, unknown>> {
  return request('/v1/me', { method: 'PATCH', body });
}

export function getMeStats(): Promise<MeStats> {
  return request<MeStats>('/v1/me/stats');
}

export function getMeConcepts(): Promise<ConceptMastery[]> {
  return request<ConceptMastery[]>('/v1/me/concepts');
}

export function getMeSessions(limit?: number): Promise<MeSessionSummary[]> {
  return request<MeSessionSummary[]>(`/v1/me/sessions${limit ? `?limit=${limit}` : ''}`);
}

export function getMeAccuracyHistory(from?: string, to?: string): Promise<AccuracyHistoryDay[]> {
  const params = new URLSearchParams();
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  const qs = params.toString();
  return request<AccuracyHistoryDay[]>(`/v1/me/accuracy-history${qs ? `?${qs}` : ''}`);
}

export function postDispute(exerciseId: string, version: number, body: DisputeRequest): Promise<DisputeResponse> {
  return request<DisputeResponse>(`/v1/exercises/${exerciseId}/v/${version}/dispute`, {
    method: 'POST',
    body,
  });
}

export function getMeActivity(from?: string, to?: string): Promise<ActivityDay[]> {
  const params = new URLSearchParams();
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  const qs = params.toString();
  return request<ActivityDay[]>(`/v1/me/activity${qs ? `?${qs}` : ''}`);
}

export function getSessionTodayReview(): Promise<SessionReviewResponse> {
  return request<SessionReviewResponse>('/v1/session/today/review');
}

export function postReview(body: ReviewRequest): Promise<ReviewResponse> {
  return request<ReviewResponse>('/v1/me/review', { method: 'POST', body });
}

export function getReviewStatus(): Promise<ReviewStatusResponse> {
  return request<ReviewStatusResponse>('/v1/me/review');
}
