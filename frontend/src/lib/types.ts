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
}

export interface ConceptMastery {
  concept: string;
  mastery: number;
  attempts: number;
  next_review_at: string;
}

export type ExerciseType = 'spot_the_bug' | 'trace' | 'summarize';
export type DifficultyBand = 'easy' | 'medium' | 'hard' | 'boss';

export interface ReasonOption {
  id: string;
  text: string;
}

export interface TraceChoice {
  id: string;
  text: string;
}

export interface SessionExercisePayload {
  code: string;
  context_note: string;
  answer_mode?: string | null;
  reason_options?: ReasonOption[] | null;
  question?: string | null;
  choices?: TraceChoice[] | null;
  max_words?: number | null;
}

export interface SessionExercise {
  slot: number;
  exercise_id: string;
  version: number;
  type: ExerciseType;
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

export type Answer =
  | { line: number; reason_id: string }
  | { choice_id: string }
  | { text: string };

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

export interface SummarizeExplanation {
  summary: string;
  principle: string;
}

export interface SummarizeReveal {
  explanation: SummarizeExplanation;
}

export type Reveal = STBReveal | TraceReveal | SummarizeReveal;

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
}

export type AttemptStatus = 'graded' | 'grading_pending' | 'grading_failed';

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
