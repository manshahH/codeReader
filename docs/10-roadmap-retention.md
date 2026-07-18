# 10 : Roadmap (Retention & Gamification)

Status: A1 IS BUILT AND SHIPPED (2026-07-18). Everything from A2 onward is still
planning. This is the "what we build next" doc; `HANDOFF.md` is the "what is
already built" doc. Read both before starting. **A2 (email capture) is next.**

The MVP proved the hard part (execution-validated content, the daily loop). This
layer is the retention engine. It is backed by research on Duolingo, Habitica,
Strava, Apple Fitness, Codewars/LeetCode/Exercism, brain-training and calm apps,
plus the workplace-gamification and developer-assessment literature. Sources and
full rationale are in the chat thread that produced this doc; the load-bearing
conclusions are inlined below.

## North star and the two rules that govern every mechanic

1. Retention of already-active users is the growth lever, not acquisition
   (Duolingo: current-user retention had roughly 5x the DAU impact of the next
   lever). Optimise for the returning developer.
2. Our audience is working professionals, so we take Duolingo's STRUCTURE but not
   its emotional engine (guilt, fear-of-loss, streak anxiety). Two hard rules:
   - The scored metric must BE the real skill (comprehension quality), never a
     volume count. A count rebuilds LeetCode's burnout and false-progress trap.
   - Core loop is built on mastery, curiosity and meaning. Streak-loss, scarcity
     and competition are light seasoning only, and competition is always opt-in.

## What already exists as a seam (build on these, do not re-plumb)

- `users.level` (junior / mid / senior): pathway levels.
- `users.reminder_local_time`: reminder scheduling. No email is captured yet.
- `exercises.language`: currently CHECK-locked to 'python'; multi-language is a
  content problem, not a schema rewrite.
- `exercises.difficulty_authored` (1-10) + `difficulty_empirical`: difficulty ramp.
- `exercises.tags[]` + `concepts[]`: tracks and per-topic filtering.
- `user_concept_state` (mastery, next_review_at): adaptive difficulty + spaced
  repetition are already modelled; the scheduler just is not wired to the session
  builder yet.
- `exercise_stats`: percentile feedback.
- Redis sorted-set pattern (docs/02): leaderboards when we get there.

## Phase A : quick wins (low risk, mostly on existing seams)

Do these first. They move retention in weeks and answer beta-user feedback directly.

- A1 Streak safety net (**SHIPPED**, see the A1 spec section below): streak freeze, repair / earn-back, grace days, and a
  "celebrate the return" tone instead of guilt. Decouple the streak from any hard
  daily goal (one exercise = one day). Auto-freeze everyone on a service outage
  (Duolingo's "big red button"). Why: loss aversion without a safety net churns a
  busy-professional audience; freezes raise 7-day-plus streak length ~48%.
- A2 Email capture: an in-app profile prompt ("add email for reminders and your
  weekly recap"). Why: GitHub OAuth scope is `read:user`, so we have no email, and
  the whole notification channel depends on one. Seam: add a verified email field.
- A3 Reminders + weekly recap email: built on `reminder_local_time`. Optimise copy
  and timing, never frequency ("protect the channel"), and drop all guilt tone.
- A4 Peek at tomorrow: a teaser of tomorrow's set. Why: a reason to return that the
  streak cannot supply; cheap dopamine (requested by a beta user).
- A5 Personal cheat sheet: let a user save an explanation or snippet, tagged by
  topic, and revisit it. Why: this is the habit-loop "investment" step and the
  ownership drive; it turns 5-minute sessions into a durable personal reference.
  Strong retention feature and a natural Pro gate. (Requested by a beta user.)
- A6 Soft language / stack focus: a preference (Python / TS / ...), NOT a hard
  filter, so it never starves the adaptive path or spaced repetition.

## Phase B : the structured path (the headline)

A single recommended next step, easy-to-hard, but adapted for a pro audience.

- B1 Placement test: adaptive, starts easy and ramps as answers come in correct.
  Why: a senior must not be forced through trivial content (Duolingo optimised for
  beginners and knowingly frustrated experts; we cannot).
- B2 Adaptive daily set: keep "3 problems a day" as the visible frame (a ring to
  close), but pick difficulty per user from `user_concept_state.mastery` +
  `difficulty_empirical` to hold a target success rate.
- B3 Tracks / pathways: backend, frontend, security, devops, logic. Start with 2-3
  DEEP tracks, not 5 thin ones (the shallow-format ceiling is why bite-size rivals
  plateau). Choice of track is real autonomy; order within a track is not, so
  present one recommended next step inside a track.
- B4 Test-out / skip so seniors clear easy rungs fast.
- B5 Endowed progress: never start a user or a new track at literal zero; pre-fill
  step 1 (endowed-progress effect roughly doubled completion in field studies).

## Phase C : identity and motivation layer (non-pressuring)

- C1 XP tied to difficulty and mastery, never raw volume (the anti-LeetCode rule).
- C2 Levels + a Codewars-style rank ladder, framed as competence ("you can now read
  recursive code fluently"), not as points.
- C3 Achievements: some unexpected, all informational (unexpected / informational
  rewards preserve intrinsic motivation; controlling ones crowd it out).
- C4 Opt-in friends leaderboard: scoped (friends only or plus-or-minus 5 around the
  user), hide the bottom, calm mode default-off, and reward consistency, not only
  talent (Strava's local-legend pattern) so ordinary users can win.
- C5 More languages (content-gated; relax the `language` CHECK when content exists).

## Phase D : the business

- D1 B2B, REDESIGNED. See the trap below. Ship company-as-entity (opt-in
  company-vs-company city board), private self-referential progress inside a
  company, and org-level AGGREGATE, UNNAMED dashboards for employers. Do NOT ship a
  public ranking of named employees across companies.
- D2 Interview / assessment mode: "read this code, find the bug / explain it" as a
  work-sample hiring test. This is the real revenue and the strongest-validated
  idea: code reading is ~58% of a developer's time and roughly 10:1 versus writing;
  work-sample tests are among the best predictors of job performance; and "explain
  your own code" is the industry's own recommended anti-AI-cheat check. No incumbent
  (HackerRank, Codility, CodeSignal) has a first-class comprehension-assessment
  product. Price per assessment; ATS integration and proctoring are the enterprise
  upsell. `predict_the_fix` is already a good work-sample spine for this.

## The one trap (explicit non-goal)

A public, city-wide, cross-company leaderboard of NAMED INDIVIDUALS ranked by skill
is the single highest-risk feature proposed, and we are not building it. It
recombines stack ranking (Microsoft killed it in 2013 as its "most destructive
process"), workplace surveillance (Microsoft's Productivity Score was stripped of
names within weeks of a 2020 backlash), and GDPR profiling (ranking employees by
work performance is profiling; employee consent is not a valid basis at work). Every
close precedent was reversed. It also exposes an employee's performance to
competitors and recruiters, which enterprise buyers will reject. The safer design in
D1 serves the same ambition without any of this.

## Phase A1 spec : streak safety net

Goal: keep the streak's habit pull while removing its anxiety, for a
busy-professional audience. A missed day should be a non-event, not a loss.

### What already exists (build on these, do not add tables)

- `user_stats.streak_freezes` (int, default 0): the freeze balance. Currently
  unused.
- `streak_events.event` CHECK already allows `freeze_used`, `repaired`, and
  `adjusted`, alongside `extended` / `reset`. No migration needed for events.
- `attempts/service.py::_update_streak_and_attempt_count(db, user, today)`: the one
  function that transitions the streak. Today it does: same-day -> no-op; gap of
  exactly 1 day or first-ever -> `extended`; any larger gap -> `reset` to 1. It does
  NOT consult `streak_freezes`. This function is where freezes plug in.
- A submission already counts toward the day regardless of correctness (D-19), so
  "one exercise = one day" and "decoupled from a hard goal" are ALREADY satisfied.
  Do not add an XP/goal threshold to the streak.
- `jobs/streak_recon.py` already writes `repaired` / `adjusted` rows for timezone
  edge cases; reuse its transaction pattern.

### Behaviour

1. Freeze accrual (config-driven, all knobs in config.py):
   - New users start with `STREAK_FREEZE_START = 2` (Duolingo A/B: 2 beat 1; 3 did
     not beat 2). Cap `STREAK_FREEZE_MAX = 2`.
   - Earn +1 freeze on every `STREAK_FREEZE_EARN_EVERY = 10` consecutive active
     days, never exceeding the cap. Accrual writes an `adjusted` streak_event with a
     note so the ledger explains the balance.
2. Freeze consumption (automatic, silent, inside the gap branch):
   - When there is a gap of N missed local days (N >= 1) and `streak_freezes >= N`
     and `N <= STREAK_FREEZE_MAX`, consume N freezes, fill each missed day with a
     `freeze_used` streak_event (one row per filled `local_date`), keep
     `current_streak`, and then apply today's `extended` transition normally. Net
     effect: the streak survives and the balance drops by N.
   - If the gap exceeds the freeze balance (or the cap), fall through to the current
     `reset` behaviour unchanged.
3. Repair / earn-back (opt-in, bounded, one-shot):
   - After a `reset`, the user may restore the streak value they just lost by
     completing a session within `STREAK_REPAIR_WINDOW_H = 48` hours of the reset.
   - New endpoint `POST /v1/streak/repair` (idempotent): if within the window and a
     restorable reset exists, set `current_streak` back to the pre-reset value plus
     the days since, write a `repaired` streak_event, and return the new value.
     Outside the window or with no restorable reset: 409, no change.
   - A reset can be repaired at most once. The most recent `reset` row is the
     restorable anchor.
4. Celebrate the return, never guilt: after a `reset`, the dashboard and
   session-complete reveal show a warm "welcome back, let's start a new streak"
   state, and, if a repair is available, a single non-nagging "restore your N-day
   streak" affordance. No guilt copy anywhere ("you let Duo down" is the anti-goal).
5. Outage freeze (ops action, the "big red button"): an admin endpoint that, for a
   given `local_date`, fills that day for all active users with a `freeze_used`
   (note: 'outage') WITHOUT spending their balance, so a service outage never costs
   a streak. Mirror `streak_recon.py`'s bulk pattern; guard behind the existing
   admin auth.

### API additions

- `POST /v1/streak/repair` -> `{ current_streak, repaired: bool }`. Idempotent.
- Extend the profile/stats payload to expose `streak_freezes` and a
  `repair_available` boolean (the client needs it to render the affordance). The
  serializer allowlist must be updated to include only these, not internal fields.
- Admin: `POST /admin/streak/outage-freeze { local_date }` behind admin auth.

### Acceptance criteria (every gate gets a negative test, per CLAUDE.md)

- A miss of 1 day with 1 freeze: streak preserved, balance -1, exactly one
  `freeze_used` row for the missed date, then `extended` for today. Negative: a miss
  of 2 days with 1 freeze still `reset`s (freeze must NOT partially cover).
- Freezes never exceed `STREAK_FREEZE_MAX` regardless of streak length. Negative:
  earning a freeze at the cap writes no row and does not exceed the cap.
- Repair inside 48h restores the exact lost value; a second repair of the same reset
  is a 409. Negative: repair outside 48h is a 409 and does not change the streak.
- Outage-freeze fills the day for all users and spends zero balance. Negative: it
  does not extend the streak of a user who was already inactive before the outage
  window in a way that manufactures a streak they never had.
- Invariant 5 still holds: every streak transition writes exactly the right
  streak_events rows and no duplicates. Verify against the existing unique index on
  `streak_events(user_id, local_date)`; confirm it permits the new `freeze_used` /
  `repaired` rows (it is currently reasoned about for `extended`/`reset` only, see
  the comment near service.py:450). If the index would block backfilled rows, that
  is a schema decision to record as a D-entry FIRST.
- Idempotency: `POST /v1/streak/repair` replayed is byte-identical (reuse the
  attempts idempotency discipline).

### Out of scope for A1

XP, levels, leaderboards, the adaptive path, email, reminders. A1 is purely the
streak's forgiveness mechanics. Email/reminders are A2/A3.

### A1 as actually built (2026-07-18)

Shipped as specced above, with three divergences and one deferral, all recorded
as decisions rather than absorbed silently.

- **D-116** is the load-bearing one. The spec's consumption rule is balance-only,
  but the outage freeze fills days WITHOUT spending balance, so the two rules
  contradict each other on any gap they both touch. Resolution: a "covered day"
  is read from the `streak_events` ledger, never inferred from the balance. The
  balance pays only for the UNCOVERED remainder, and the cap applies to that
  remainder too, so outage-covered days are free. D-116 also records that
  `streak_recon.py` has no bulk pattern to mirror (it is a single-user helper),
  that `streak_freezes` was already exposed, and that `repaired` rows needed an
  explicit anchor because `streak_recon.py` already writes that event kind.
- **D-117**: both `.env.example` files are drift-checked now. The root one had
  already drifted.
- **D-118**: one-time backfill of the starting freeze balance for pre-A1
  accounts, via `POST /admin/streak/grant-initial-freezes`. Run once after
  deploy.
- The restore value is the unbroken counterfactual (value lost + the run built
  since the reset), read entirely from the ledger. An elapsed-days formula is
  wrong in both directions: it drops the reset day, which is itself an active
  day, and over-credits any day the user was not active.

**DEFERRED, and the reason it is not a bug:** the spec says the "celebrate the
return" state appears on "the dashboard and session-complete". **There is no
session-complete screen.** `frontend/src/routes/Session.tsx` redirects to the
Dashboard once the last exercise is done, and a `latestStreak` state there was
written but never read (removed in A1, with a comment left at the write site).
So the welcome-back state lives on the Dashboard, and the per-attempt reveal
carries the warmed reset copy. Building a real session-complete screen is its
own piece of work and a natural home for a session-level streak summary,
`first_completed_session` (already in the API and unused by the client), and the
A4 "peek at tomorrow" teaser. Pick it up with A4 or as a standalone UI task.

## Open decisions (to resolve before building the relevant phase)

- Which 2-3 tracks launch first (depends on where content is deepest today).
- Free vs Pro split for the cheat sheet, extra sessions, and languages.
- Whether XP is visible to the user at all, or only the competence framing.
- The exact adaptive-difficulty target success rate (Duolingo's "Birdbrain" band).
- Assessment mode as a separate product surface vs a mode inside the app.
