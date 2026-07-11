// One Idempotency-Key per exercise serve (docs/05 section 1). Cached per
// exercise_id so a retried submit (network hiccup, poll-triggered resend)
// reuses the same key instead of minting a new attempt.
const keysByExercise = new Map<string, string>();

export function idempotencyKeyFor(exerciseId: string): string {
  const existing = keysByExercise.get(exerciseId);
  if (existing) return existing;
  const key = crypto.randomUUID();
  keysByExercise.set(exerciseId, key);
  return key;
}
