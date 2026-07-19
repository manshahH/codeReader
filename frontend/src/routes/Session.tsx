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
import { NarrowSession, PinnedSelection } from '../components/session/NarrowSession';
import { primaryDocuments, type CodeRange } from '../lib/code/model';
import { useIsNarrow } from '../lib/code/viewerPreferences';
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
  // D-134: which of the two full-screen narrow states is showing. Reading
  // first, always -- the code is what you came for.
  const [narrowMode, setNarrowMode] = useState<'reading' | 'answering'>('reading');

  // D-129 decision 1: the session tracks a RANGE, not a row. spot_the_bug
  // still answers with a line number, which is read off the range's start at
  // submit time -- so a future type that selects a sub-expression changes what
  // it puts in `answer`, not how selection is stored.
  const [selection, setSelection] = useState<CodeRange | null>(null);
  const [selectedReasonId, setSelectedReasonId] = useState<string | null>(null);
  const [selectedChoiceId, setSelectedChoiceId] = useState<string | null>(null);
  const [summaryText, setSummaryText] = useState('');

  // Called with the other hooks, above this component's early returns: the
  // layout branch is chosen far below, but hook order cannot depend on it.
  const isNarrow = useIsNarrow();

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
    setSelection(null);
    // Per-exercise: arriving at the next exercise must start in the reading
    // state, never mid-answer on code you have not seen.
    setNarrowMode('reading');
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
      ? selection !== null && selectedReasonId !== null
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
    if (exercise.type === 'spot_the_bug')
      answer = { line: (selection as CodeRange).start.line, reason_id: selectedReasonId as string };
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

  // D-130. The two arrangements share these fragments verbatim: mobile is a
  // different ARRANGEMENT of the same components, not a second implementation
  // of them. Building them here (rather than inlining twice) is also what
  // keeps the wide branch byte-identical to what it rendered before -- there
  // is only one copy to drift.
  const answerControls =
    exercise.type === 'spot_the_bug' ? (
      <SpotTheBugAnswer
        payload={exercise.payload}
        selectedReasonId={selectedReasonId}
        onSelectReason={setSelectedReasonId}
      />
    ) : exercise.type === 'trace' ? (
      <TraceAnswer payload={exercise.payload} selectedChoiceId={selectedChoiceId} onSelectChoice={setSelectedChoiceId} />
    ) : exercise.type === 'predict_the_fix' ? (
      <PredictTheFixAnswer payload={exercise.payload} selectedChoiceId={selectedChoiceId} onSelectChoice={setSelectedChoiceId} />
    ) : (
      <SummarizeAnswer payload={exercise.payload} text={summaryText} onChangeText={setSummaryText} />
    );

  const submitRow = (
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
  );

  const gradingStatus =
    phase === 'grading_pending' ? (
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
    ) : null;

  // D-134 labels. The reading action says what happens next, and the
  // answering hint says what is still outstanding -- neither is decoration:
  // they are the only place the reader is told what the toggle is for.
  const selectedChoiceText =
    exercise.type === 'trace' && selectedChoiceId
      ? ((exercise.payload.choices ?? []).find((c) => c.id === selectedChoiceId)?.text ?? null)
      : null;

  const readingActionLabel =
    exercise.type === 'spot_the_bug'
      ? selection === null
        ? 'Tap the buggy line, or pick a reason'
        : `Line ${selection.start.line} selected — pick a reason`
      : isValid
        ? 'Review your answer'
        : 'Answer';

  const answeringHint =
    exercise.type === 'spot_the_bug' && selection === null
      ? 'No line selected yet'
      : isValid
        ? 'Ready to check'
        : 'Choose an answer';

  const answering = phase === 'answering' || phase === 'submitting';
  const inAnswerPhase =
    answering || phase === 'grading_pending' || phase === 'grading_failed' || phase === 'grading_timeout';

  if (isNarrow) {
    return (
      <div
        // Code owns the viewport (D-130): the column is exactly the visible
        // height, the code region is the only thing that grows, and the sheet
        // sits under it. dvh not vh, so a collapsing mobile URL bar cannot push
        // the sheet's controls off-screen.
        className="mx-auto flex h-full max-h-[100dvh] w-full flex-col overflow-hidden"
        style={{ paddingTop: 'var(--safe-top)', paddingLeft: 'var(--safe-left)', paddingRight: 'var(--safe-right)' }}
      >
        <div className="shrink-0 px-page pt-3">
          <SessionProgressRail exercises={session.exercises} currentIndex={currentIndex} />
          <div className="mt-3 flex items-baseline justify-between text-sm text-ink-muted">
            <span className="capitalize">{exercise.type.replace(/_/g, ' ')}</span>
            <span className="text-xs">{exercise.difficulty_band}</span>
          </div>
        </div>

        <ErrorBoundary
          key={currentIndex}
          fallback={
            <div className="flex flex-col gap-4 px-page py-6">
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
          {inAnswerPhase ? (
            <NarrowSession
              mode={narrowMode}
              reading={
                <>
                  <p className="line-clamp-2 shrink-0 px-page pt-2 text-sm text-ink-muted">
                    {exercise.payload.context_note}
                  </p>
                  <div className="flex min-h-0 flex-1 flex-col px-page pb-2 pt-1">
                    <CodeBlock
                      documents={primaryDocuments(exercise.payload)}
                      selection={exercise.type === 'spot_the_bug' ? selection : null}
                      onSelectRange={
                        exercise.type === 'spot_the_bug'
                          ? (range) => {
                              // Tapping a line IS the first half of the answer,
                              // so it carries you to the second half with the
                              // line already selected. Going back preserves it.
                              setSelection(range);
                              setNarrowMode('answering');
                            }
                          : undefined
                      }
                      fillsViewport
                      // D-132: tappable rows cost roughly half the visible
                      // lines, so only the type that answers BY TAPPING A LINE
                      // pays for them, and only while it is answering.
                      tapSizedRows={exercise.type === 'spot_the_bug' && answering}
                    />
                  </div>
                  {/* D-134, and a recorded docs/08 exception: only trace, and
                      only once something is selected. */}
                  {exercise.type === 'trace' && selectedChoiceText ? (
                    <PinnedSelection label="Your answer" value={selectedChoiceText} />
                  ) : null}
                </>
              }
              readingAction={
                <button
                  type="button"
                  onClick={() => setNarrowMode('answering')}
                  className="min-h-tap w-full rounded-soft bg-action px-6 py-3 font-ui text-base font-medium text-surface-reading transition-colors duration-fast hover:bg-action-hover"
                  style={{ touchAction: 'manipulation' }}
                >
                  {readingActionLabel}
                </button>
              }
              answeringNav={
                <div className="flex items-center justify-between gap-3">
                  <button
                    type="button"
                    onClick={() => setNarrowMode('reading')}
                    className="-ml-2 inline-flex min-h-tap items-center gap-2 rounded-soft px-2 text-sm text-action transition-colors duration-fast hover:text-action-hover"
                    style={{ touchAction: 'manipulation' }}
                  >
                    <span aria-hidden="true" className="font-code">
                      &#8592;
                    </span>
                    Back to the code
                  </button>
                  <span className="truncate text-xs text-ink-muted">{answeringHint}</span>
                </div>
              }
              answering={
                answering ? (
                  <div className="flex flex-col gap-4">
                    {answerControls}
                    {submitError ? <p className="text-sm text-incorrect">{submitError}</p> : null}
                  </div>
                ) : (
                  gradingStatus
                )
              }
              answeringSubmit={answering ? submitRow : <div className="min-h-tap" />}
            />
          ) : attempt && userAnswer ? (
            <div className="min-h-0 flex-1 overflow-y-auto px-page pb-4">
              <Reveal
                exercise={exercise}
                attempt={attempt}
                userAnswer={userAnswer}
                onNext={handleNext}
                onDispute={() => setDisputeOpen(true)}
              />
            </div>
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
            {/* The PRIMARY document only. The payload can carry several (a
                predict_the_fix payload carries the failing test and every
                candidate fix too), but this column shows the code under study;
                the other documents are rendered by the answer component, in
                their own places. */}
            <CodeBlock
              documents={primaryDocuments(exercise.payload)}
              selection={exercise.type === 'spot_the_bug' ? selection : null}
              onSelectRange={exercise.type === 'spot_the_bug' ? setSelection : undefined}
            />
          </div>

          {/* Right Column: Interaction */}
          <div className="flex-1 overflow-y-auto pr-2 flex flex-col gap-6">
            <p className="text-sm text-ink-muted">{exercise.payload.context_note}</p>

            {phase === 'answering' || phase === 'submitting' ? (
              <>
                {answerControls}
                {submitError ? <p className="text-sm text-incorrect">{submitError}</p> : null}
                {submitRow}
              </>
            ) : (
              gradingStatus
            )}
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
