# 00 : Product

## One-liner
Duolingo for the half of engineering nobody trains: reading, reviewing, and
debugging code, especially AI-generated code. Daily 5-10 minute sessions for
working software developers.

## Why now
Professionals spend ~60% of their time understanding code, not writing it, and
the ratio is rising as AI writes more first drafts. AI output is syntactically
perfect and semantically wrong in subtle ways; the market-differentiating skill
in 2026 is verifying, reviewing, and debugging code you did not write. Writing
practice is saturated (LeetCode, Codewars, Exercism, HackerRank). Reading
practice has no serious product.

## Competitive landscape (researched Jul 2026)
- codereading.club (Felienne Hermans): manual group meetups, validates demand,
  not a product.
- spotthebug.dev: closest competitor; one daily puzzle, streaks, no curriculum,
  no personalization, no real-codebase content. Thin hobby site.
- LeetCode/Codewars/Exercism/HackerRank: writing-first; debugging only as a
  side effect of failing tests.
- Mimo/CodenQuest: beginner syntax learning, not comprehension for working devs.

Gap we occupy: real-world code + daily habit loop + comprehension/debugging as
the explicit skill + working developers as the audience.

## Exercise types (the skill, decomposed)
1. trace: mentally execute; what does this print / what is x after line N
2. summarize: describe what this does in one sentence (rubric graded)
3. spot_the_bug: find the planted or real bug, line + reason
4. predict_the_fix: given failing test, pick/write minimal fix (post-MVP)
5. review_the_pr: judge an AI-generated diff, approve or request changes (post-MVP, flagship)
6. navigate: where would you look first, given a file tree (post-MVP)
7. smell_the_intent: docstring vs actual behavior mismatch (post-MVP)

MVP ships 1-3 in Python only.

## Core loop
Onboard (language, level, goal) -> daily session of 3-5 mixed exercises with
one boss -> instant explanation after each answer (the explanation IS the
product) -> percentile stat ("only 31% caught this") -> streak -> weekly
long-read of famous real code (post-MVP) -> skill graph with spaced repetition.

## Retention mechanics
Spaced repetition on weak concepts (the real engine), streaks + freezes (the
visible engine), percentile feedback per exercise, timed push at user-chosen
time with a teaser, weekly recap email, leagues and a public "Reader Rank"
post-MVP.

## Business model

> SUPERSEDED BY D-145. The paragraph below is the ORIGINAL plan and is kept for
> history; do not read it as a current tier decision. Two specifics are now
> wrong and dangerous if acted on: (1) it names a SINGLE "Pro" tier at a fixed
> price, but D-145 decision 1 says there will be MULTIPLE paid tiers and the
> split is deferred until per-feature usage data exists; (2) it puts SPACED
> REPETITION behind that tier, but spaced repetition is SHIPPED and FREE and is
> the retention engine, so moving it would strip a core mechanic from every
> existing user under D-145 decision 3 (no grandfathering). Everything is free
> today. See D-145 for the settled shape.

Free: 1 daily session, streaks. Pro ($6-9/mo): unlimited sessions, all
languages, rubric-graded free text, spaced repetition, AI-verification track,
interview mode. Teams ($8-12/user/mo, the real revenue): dashboards, onboarding
tracks, exercises generated from the customer's own repo history, review
calibration. Later: hiring assessments.

## Pre-mortem (ranked kill risks)
1. Content quality collapse: one wrong answer on HN front page. Mitigation:
   execution-validated ground truth only, dispute button, fast pull.
2. Novelty churn at week 4. Mitigation: spaced repetition + skill graph +
   weekly flagship content.
3. "I'll just ask Claude": positioning is verify-AI, not learn-to-code.
4. LeetCode adds debugging: speed and focus is the defense.

## Explicit non-goals
No in-browser code writing/execution editor. No beginner curriculum. No AI
chat tutor. No 50 languages at launch.
