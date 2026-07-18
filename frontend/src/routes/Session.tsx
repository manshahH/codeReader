import { useCallback, useEffect, useRef, useState } from 'react';

import { DisputeModal } from '../components/DisputeModal';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { Navigate } from 'react-router-dom';
import { CodeBlock } from '../components/gutter/CodeBlock';
import { Reveal } from '../components/session/Reveal';
import { SessionProgressRail } from '../components/session/SessionProgressRail';
import { PredictTheFixAnswer } from '../components/session/PredictTheFixAnswer';
import { SpotTheBugAnswer } from '../components/session/SpotTheBugAnswer';
import { SummarizeAnswer } from '../components/session/SummarizeAnswer';
import { TraceAnswer } from '../components/session/TraceAnswer';
import { ApiError, getAttemptPoll, getSessionToday, postAttempt } from '../lib/api';
import { idempotencyKeyFor } from '../lib/idempotency';
import type { Answer, AttemptResponse, SessionResponse } from '../lib/types';

type Phase = 'answering' | 'submitting' | 'grading_pending' | 'revealed' | 'grading_failed' | 'grading_timeout';

const DEFAULT_POLL_SECONDS = 3;
// A stuck grade must never freeze the session: after this long we stop
// polling, tell the user their streak counted, and let them move on. The
// backend retry job resolves the grade eventually; it just won't be shown
// in this sitting.
const MAX_POLL_MS = 2 * 60 * 1000;

export function Session() {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>('answering');
  const [attempt, setAttempt] = useState<AttemptResponse | null>(null);
  const [userAnswer, setUserAnswer] = useState<Answer | null>(null);
  const [correctCount, setCorrectCount] = useState(0);
  const [attemptedThisLoad, setAttemptedThisLoad] = useState(0);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [disputeOpen, setDisputeOpen] = useState(false);

  const [selectedLine, setSelectedLine] = useState<number | null>(null);
  const [selectedReasonId, setSelectedReasonId] = useState<string | null>(null);
  const [selectedChoiceId, setSelectedChoiceId] = useState<string | null>(null);
  const [summaryText, setSummaryText] = useState('');

  const startTimeRef = useRef(Date.now());
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const pollStartRef = useRef(0);

  useEffect(() => {
    // The session content is the only fetch this screen needs. Reaching
    // /session is already the user's deliberate choice (the dashboard CTA);
    // the player opens on the first unattempted exercise, and a reload
    // mid-session resumes where they left off.
    getSessionToday()
      .then((body) => {
        setSession(body);
        const firstUnattempted = body.exercises.findIndex((e) => !e.attempted);
        const idx = firstUnattempted === -1 ? body.exercises.length : firstUnattempted;
        setCurrentIndex(idx);
        startTimeRef.current = Date.now();
      })
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : 'Could not load today’s session.'));
    return () => {
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    };
  }, []);

  const resetDraft = useCallback(() => {
    setSelectedLine(null);
    setSelectedReasonId(null);
    setSelectedChoiceId(null);
    setSummaryText('');
    setSubmitError(null);
    startTimeRef.current = Date.now();
  }, []);

  const applyGraded = useCallback((response: AttemptResponse) => {
    setAttempt(response);
    // No session-complete screen exists yet (this route redirects to the
    // Dashboard when the last exercise is done), so there is nowhere to show a
    // session-level streak summary. Reveal reads attempt.streak directly for
    // the per-attempt line. A `latestStreak` state that was only ever written,
    // never read, lived here until A1; see docs/10's deferred list.
    if (response.status === 'graded') {
      if (response.is_correct) setCorrectCount((c) => c + 1);
      setAttemptedThisLoad((c) => c + 1);
      setPhase('revealed');
    } else if (response.status === 'skipped') {
      // Counts as a submission (D-19), never as correct (D-93).
      setAttemptedThisLoad((c) => c + 1);
      setPhase('revealed');
    } else if (response.status === 'grading_pending') {
      setPhase('grading_pending');
    } else {
      setAttemptedThisLoad((c) => c + 1);
      setPhase('grading_failed');
    }
  }, []);

  const stopPollingForThisSitting = useCallback(() => {
    setAttemptedThisLoad((c) => c + 1);
    setPhase('grading_timeout');
  }, []);

  const pollAttempt = useCallback(
    (attemptId: number, delaySeconds: number) => {
      pollTimeoutRef.current = setTimeout(async () => {
        if (Date.now() - pollStartRef.current >= MAX_POLL_MS) {
          stopPollingForThisSitting();
          return;
        }
        try {
          const { body, retryAfterSeconds } = await getAttemptPoll(attemptId);
          if (body.status === 'grading_pending') {
            pollAttempt(attemptId, retryAfterSeconds ?? DEFAULT_POLL_SECONDS);
          } else {
            applyGraded(body);
          }
        } catch {
          pollAttempt(attemptId, DEFAULT_POLL_SECONDS);
        }
      }, delaySeconds * 1000);
    },
    [applyGraded, stopPollingForThisSitting],
  );

  if (loadError) {
    return <p className="p-6 text-incorrect">{loadError}</p>;
  }
  if (!session) {
    return <p className="p-6 text-ink-muted">Loading today’s session…</p>;
  }
  if (session.exercises.length === 0) {
    return <p className="p-6 text-ink-muted">Nothing to read just yet. Check back in a little while.</p>;
  }
  if (currentIndex >= session.exercises.length) {
    return <Navigate to="/" replace />;
  }

  const exercise = session.exercises[currentIndex];

  const isChoiceType = exercise.type === 'trace' || exercise.type === 'predict_the_fix';
  const isValid =
    exercise.type === 'spot_the_bug'
      ? selectedLine !== null && selectedReasonId !== null
      : isChoiceType
        ? selectedChoiceId !== null
        : summaryText.trim().length > 0 && summaryText.trim().split(/\s+/).length <= (exercise.payload.max_words ?? 60);

  const submitAnswer = async (answer: Answer) => {
    setUserAnswer(answer);
    setPhase('submitting');
    setSubmitError(null);
    try {
      const key = idempotencyKeyFor(exercise.exercise_id);
      const timeTakenMs = Date.now() - startTimeRef.current;
      const response = await postAttempt(key, {
        exercise_id: exercise.exercise_id,
        exercise_version: exercise.version,
        answer,
        time_taken_ms: timeTakenMs,
      });
      applyGraded(response);
      if (response.status === 'grading_pending') {
        pollStartRef.current = Date.now();
        pollAttempt(response.attempt_id, DEFAULT_POLL_SECONDS);
      }
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : 'Could not submit that. Try again.');
      setPhase('answering');
    }
  };

  const handleSubmit = () => {
    let answer: Answer;
    if (exercise.type === 'spot_the_bug') answer = { line: selectedLine as number, reason_id: selectedReasonId as string };
    else if (isChoiceType) answer = { choice_id: selectedChoiceId as string };
    else answer = { text: summaryText.trim() };
    submitAnswer(answer);
  };

  const handleSkip = () => submitAnswer({ skipped: true });

  const handleNext = () => {
    resetDraft();
    setAttempt(null);
    setUserAnswer(null);
    setPhase('answering');
    setCurrentIndex((i) => i + 1);
  };

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col gap-6 px-4 py-8">
      <div className="shrink-0">
        <SessionProgressRail exercises={session.exercises} currentIndex={currentIndex} />

        <div className="mt-6 flex items-center justify-between text-sm text-ink-muted">
          <span className="capitalize">{exercise.type.replace(/_/g, ' ')}</span>
          <span>{exercise.difficulty_band}</span>
        </div>
      </div>

      <ErrorBoundary
        key={currentIndex}
        fallback={
          <div className="flex flex-col gap-4">
            <p className="text-sm text-incorrect">
              Something went wrong showing this exercise. Skip it to keep your session going.
            </p>
            <button
              type="button"
              onClick={handleNext}
              className="self-start rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
            >
              Skip this exercise
            </button>
          </div>
        }
      >
      {phase === 'answering' || phase === 'submitting' || phase === 'grading_pending' || phase === 'grading_failed' || phase === 'grading_timeout' ? (
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-10 lg:grid-cols-2">
          {/* Left Column: Code */}
          <div className="flex-1 overflow-y-auto pr-2">
            <CodeBlock
              code={exercise.payload.code}
              selectedLine={exercise.type === 'spot_the_bug' ? selectedLine : null}
              onSelectLine={exercise.type === 'spot_the_bug' ? setSelectedLine : undefined}
            />
          </div>

          {/* Right Column: Interaction */}
          <div className="flex-1 overflow-y-auto pr-2 flex flex-col gap-6">
            <p className="text-sm text-ink-muted">{exercise.payload.context_note}</p>

            {phase === 'answering' || phase === 'submitting' ? (
              <>
                {exercise.type === 'spot_the_bug' ? (
                  <SpotTheBugAnswer
                    payload={exercise.payload}
                    selectedLine={selectedLine}
                    onSelectLine={setSelectedLine}
                    selectedReasonId={selectedReasonId}
                    onSelectReason={setSelectedReasonId}
                  />
                ) : exercise.type === 'trace' ? (
                  <TraceAnswer payload={exercise.payload} selectedChoiceId={selectedChoiceId} onSelectChoice={setSelectedChoiceId} />
                ) : exercise.type === 'predict_the_fix' ? (
                  <PredictTheFixAnswer payload={exercise.payload} selectedChoiceId={selectedChoiceId} onSelectChoice={setSelectedChoiceId} />
                ) : (
                  <SummarizeAnswer payload={exercise.payload} text={summaryText} onChangeText={setSummaryText} />
                )}
                {submitError ? <p className="text-sm text-incorrect">{submitError}</p> : null}
                <div className="flex items-center gap-4">
                  <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={!isValid || phase === 'submitting'}
                    className="rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover disabled:opacity-40"
                  >
                    {phase === 'submitting' ? 'Checking…' : 'Check answer'}
                  </button>
                  {exercise.type !== 'summarize' ? (
                    <button
                      type="button"
                      onClick={handleSkip}
                      disabled={phase === 'submitting'}
                      className="text-sm text-ink-muted underline hover:text-ink disabled:opacity-40"
                    >
                      I don't know
                    </button>
                  ) : null}
                </div>
              </>
            ) : phase === 'grading_pending' ? (
              <p className="text-sm text-ink-muted" aria-live="polite">
                Reviewing your answer…
              </p>
            ) : phase === 'grading_failed' ? (
              <div className="flex flex-col gap-4">
                <p className="text-sm text-ink-muted">We couldn’t grade this one. Your streak still counts.</p>
                <button type="button" onClick={handleNext} className="self-start rounded-soft bg-action px-6 py-3 text-base font-medium text-surface-reading">
                  Next
                </button>
              </div>
            ) : phase === 'grading_timeout' ? (
              <div className="flex flex-col gap-4">
                <p className="text-sm text-ink-muted">We’ll grade this shortly. Your streak already counted, so keep going.</p>
                <button type="button" onClick={handleNext} className="self-start rounded-soft bg-action px-6 py-3 text-base font-medium text-surface-reading">
                  Next
                </button>
              </div>
            ) : null}
          </div>
        </div>
      ) : attempt && userAnswer ? (
        <Reveal exercise={exercise} attempt={attempt} userAnswer={userAnswer} onNext={handleNext} onDispute={() => setDisputeOpen(true)} />
      ) : null}
      </ErrorBoundary>

      {disputeOpen ? (
        <DisputeModal
          exerciseId={exercise.exercise_id}
          version={exercise.version}
          attemptId={attempt?.attempt_id ?? null}
          onClose={() => setDisputeOpen(false)}
        />
      ) : null}
    </div>
  );
}
