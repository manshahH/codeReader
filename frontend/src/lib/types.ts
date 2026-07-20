// Mirrors docs/05-api-contract.md exactly. No field is invented client-side;
// what the backend allowlist doesn't send, the UI doesn't assume.

export type Level = 'junior' | 'mid' | 'senior';

export interface User {
  id: string;
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  level: Level;
  timezone: string;
  onboarded: boolean;
  /**
   * A2 email capture (D-120). `email` is the CONFIRMED address only, so it
   * stays live while `pending_email` waits: a typo never takes the current
   * address offline. `email_verified` is carried explicitly rather than
   * inferred from `email !== null` so the client is not coupled to that
   * invariant.
   */
  email: string | null;
  email_verified: boolean;
  pending_email: string | null;
  /**
   * A3 (D-137). `reminder_local_time` is "HH:MM" or null, and null means no
   * time chosen -- NOT "reminders off". Consent lives in `email_prefs`, which
   * is a separate axis on purpose (D-137(6)): a user can be opted in with no
   * time set, and the Profile card renders that differently from opted out.
   */
  reminder_local_time: string | null;
  email_prefs: EmailPrefs;
}

/**
 * Consent per email type, phrased positively. The server stores the negative (a
 * suppression row) and inverts it once, at the edge, so the client never has to.
 */
export interface EmailPrefs {
  reminders_enabled: boolean;
  recap_enabled: boolean;
}

/** The body every /v1/me/email route returns: the email slice of the user. */
export interface EmailState {
  email: string | null;
  email_verified: boolean;
  pending_email: string | null;
}

export interface RefreshResponse {
  access_token: string;
  expires_in: number;
  user: User;
}

export interface MeStats {
  current_streak: number;
  longest_streak: number;
  streak_freezes: number;
  total_attempts: number;
  total_correct: number;
  accuracy_by_type: Record<string, number>;
  last_active_local_date: string | null;
  total_sessions: number;
  /** A recent reset is still inside the repair window and unrepaired (A1). */
  repair_available: boolean;
  /** The streak value a repair would restore, or null when unavailable. */
  repair_restores_to: number | null;
}

export interface StreakRepairResponse {
  current_streak: number;
  repaired: boolean;
}

export interface MeSessionSummary {
  session_date: string;
  completed: boolean;
  exercise_count: number;
  correct_count: number;
  skipped_count: number;
  concepts: string[];
}

export interface AccuracyHistoryDay {
  date: string;
  accuracy: number;
  attempts: number;
}

export interface ConceptMastery {
  concept: string;
  mastery: number;
  attempts: number;
  next_review_at: string;
}

export type ExerciseType = 'spot_the_bug' | 'trace' | 'summarize' | 'predict_the_fix';
export type DifficultyBand = 'easy' | 'medium' | 'hard' | 'boss';

export interface ReasonOption {
  id: string;
  text: string;
}

export interface TraceChoice {
  id: string;
  text: string;
}

/** D-129: the wire form of a code document. Mirrors CodeDocument in
 * backend/app/schemas/session.py; the client-side model in lib/code/model.ts
 * re-declares the same shape for components that never touch the API. */
export interface PayloadDocument {
  id: string;
  role: 'primary' | 'failing_test' | 'choice';
  code: string;
  language: string;
  label?: string | null;
}

export interface SessionExercisePayload {
  code: string;
  /** D-129: normalized at the serialization boundary, so it is present on every
   * response the current backend serves. Optional here because a cached or
   * pre-D-129 response has only `code`; normalizeCodePayload() handles both. */
  documents?: PayloadDocument[];
  context_note: string;
  answer_mode?: string | null;
  reason_options?: ReasonOption[] | null;
  question?: string | null;
  choices?: TraceChoice[] | null;
  max_words?: number | null;
  // predict_the_fix: the failing test and its captured output; `choices`
  // carries the candidate fixes (id + code).
  failing_test?: string | null;
  test_output?: string | null;
}

export interface SessionExercise {
  slot: number;
  exercise_id: string;
  version: number;
  type: ExerciseType;
  concepts: string[];
  language: string;
  difficulty_band: DifficultyBand;
  est_time_s: number;
  is_boss: boolean;
  attempted: boolean;
  payload: SessionExercisePayload;
}

export interface SessionResponse {
  session_date: string;
  completed: boolean;
  exercises: SessionExercise[];
}

export interface ActivityDay {
  session_date: string;
  completed: boolean;
}

export type ReviewVerdict = 'correct' | 'incorrect' | 'skipped' | 'grading_pending' | 'grading_failed';

export interface SessionReviewExercise {
  slot: number;
  exercise_id: string;
  version: number;
  type: ExerciseType;
  concepts: string[];
  code: string;
  context_note: string;
  answer: Answer;
  verdict: ReviewVerdict;
  reveal: Reveal | null;
}

export interface SessionReviewResponse {
  session_date: string;
  exercises: SessionReviewExercise[];
}

export interface ReviewRequest {
  rating: number;
  body?: string | null;
}

export interface ReviewResponse {
  rating: number;
  body: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewStatusResponse {
  reviewed: boolean;
  review: ReviewResponse | null;
}

export type Answer =
  | { line: number; reason_id: string }
  | { choice_id: string }
  | { text: string }
  | { skipped: true };

export interface AttemptRequest {
  exercise_id: string;
  exercise_version: number;
  answer: Answer;
  time_taken_ms?: number;
}

export interface LineNote {
  line: number;
  note: string;
}

export interface STBExplanation {
  summary: string;
  principle: string;
  line_notes: LineNote[];
}

export interface STBReveal {
  correct_lines: number[];
  correct_reason_id: string;
  explanation: STBExplanation;
}

export interface TraceTableEntry {
  line: number;
  state: string;
}

export interface WhyWrongEntry {
  choice_id: string;
  note: string;
}

export interface TraceExplanation {
  summary: string;
  principle: string;
  trace_table: TraceTableEntry[];
  why_wrong: WhyWrongEntry[];
}

export interface TraceReveal {
  correct_choice_id: string;
  explanation: TraceExplanation;
}

export interface PredictTheFixExplanation {
  summary: string;
  principle: string;
  why_wrong: WhyWrongEntry[];
}

export interface PredictTheFixReveal {
  correct_choice_id: string;
  explanation: PredictTheFixExplanation;
}

export interface SummarizeExplanation {
  summary: string;
  principle: string;
}

export interface SummarizeReveal {
  explanation: SummarizeExplanation;
}

export type Reveal = STBReveal | TraceReveal | PredictTheFixReveal | SummarizeReveal;

export interface GraderOutput {
  rubric_hits: string[];
  rubric_misses: string[];
  reference_answer: string;
}

export interface PercentileInfo {
  solve_rate: number;
  n: number;
}

export interface StreakInfo {
  current: number;
  event: 'extended' | 'reset';
}

export interface SessionProgress {
  completed: boolean;
  remaining: number;
  first_completed_session: boolean;
}

export type AttemptStatus = 'graded' | 'grading_pending' | 'grading_failed' | 'skipped';

export interface AttemptResponse {
  attempt_id: number;
  status: AttemptStatus;
  is_correct: boolean | null;
  reveal: Reveal | null;
  score?: number | null;
  grader_output?: GraderOutput | null;
  percentile: PercentileInfo | null;
  streak: StreakInfo | null;
  session: SessionProgress;
}

export type DisputeReason = 'wrong_answer' | 'ambiguous' | 'broken_code' | 'bad_explanation' | 'other';

export interface DisputeRequest {
  reason: DisputeReason;
  body: string | null;
  attempt_id: number | null;
}

export interface DisputeResponse {
  dispute_id: number;
  status: 'open' | 'accepted' | 'rejected';
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string;
  };
}
