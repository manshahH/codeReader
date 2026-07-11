Deep audit: codereader MVP
Scope covered: all docs (00–08b, ops-runbook, decision log to D-47), full backend (app/ auth, core, sessions, attempts, users, disputes, jobs, models), full pipeline (generate → gates → sandbox → semantic → dedup → publish → orchestrator → review CLI), the seed scripts, frontend src/, docker-compose, and CI.

Headline: No critical auth bypass, injection break, or sandbox escape. The auth stack (custom HS256 verify, PKCE, refresh rotation, AES-GCM), the summarize injection hardening, and the Docker sandbox are genuinely solid — I tried to break each and could not. The real dangers are elsewhere: the periodic-job layer is written but wired to nothing, so several shipped M4/M5 features silently don't run in production; and there is no working code path to pull a bad live exercise, which is the documented mitigation for the product's #1 kill risk. Those two are the ones I'd block a public beta on.

I've marked each finding NEW or KNOWN (tracked in docs/07 / deferral list).

HIGH
H1. The periodic-job layer runs nowhere — pending grades, percentiles, and partitions all silently break in prod (NEW)
Scenario: A user submits a summarize answer, the grader times out once (very likely on the tracked docker-compose.yml, which ships GRADER_MODEL: grader-model-placeholder + a fake ANTHROPIC_API_KEY). The attempt lands grading_pending. It is never resolved, because nothing ever calls resolve_pending_summarize_grades. The frontend (Session.tsx:77-93) polls GET /attempts/{id} every 3s forever with no cap, and the grading_pending phase has no "Next" button — so the session is permanently stuck on a spinner ("Reviewing your answer…").

Mechanism: main.py:53-64 lifespan starts an engine and Redis and nothing else. There is no scheduler (no APScheduler/cron/repeat_every/asyncio.create_task), and none of jobs/grading_retry.py, jobs/percentiles.py, jobs/partitions.py has a __main__ entrypoint. I grepped: their only non-test callers are the tests. Knock-on effects:

compute_exercise_stats never runs → exercise_stats stays empty → _read_percentile (attempts/service.py:94-105) always returns None → the percentile feature ("only 31% caught this," a core loop element in docs/00) is dead.
ensure_next_month_attempts_partition never runs → after 2026-08 every attempt falls into attempts_default (see H-adjacent M-partition finding below).
streak_recon and weekly_email are literally 1-line placeholders.
Why tests missed it: every test calls the job functions directly (await resolve_pending_summarize_grades(db, ...)), so the jobs are proven correct in isolation; nothing tests that the deployed app ever invokes them. M7 ("hardening + ops") is where scheduling presumably lands, but M4/M5 shipped features (pending-grade resolution, percentiles) that depend on it and are marked done.

Fix: add a jobs runner — either a lightweight in-process scheduler in lifespan (APScheduler with intervals: retry every ~30s, percentiles ~hourly, partition monthly) or a separate python -m app.jobs.run cron container added to compose/deploy. Give each job a __main__. Independently, cap the client poll loop (e.g. stop after N minutes, show "we'll grade this shortly, your streak counts") so a stuck grade doesn't freeze the session.

H2. No working path to pull a bad live exercise — the top kill-risk mitigation is uncoded (NEW)
Scenario: A live exercise has a wrong answer key (a mis-keyed reason_id that slipped the semantic gate, or a bad seed). A dispute fires. docs/00's #1 kill risk ("one wrong answer on HN front page") is mitigated by "fast pull," and ops-runbook §3 is "Pulling a disputed exercise (status flip + cache key delete)." But there is no code that can flip a live exercise's status.

Mechanism: every status change routes through update_exercise_fields (exercises/service.py:31-32), which does if exercise.status == "live": raise ExerciseImmutableError before applying any change. So kill() on a live row raises; review_cli kill on a live exercise fails. The immutability guard (D-5, meant to protect content per version) is over-broad — it also forbids lifecycle transitions (live → pulled/retired). I confirmed by grep: nothing anywhere sets status to pulled/retired/live on a live row. Pulling therefore requires hand-written SQL under incident pressure, with no cache-invalidation helper (the session:{user}:{date} Redis keys and daily_sessions rows still reference the pulled exercise for up to 36h).

Why tests missed it: M1's immutability test proves a live row can't be UPDATEd — which is exactly the behavior that also blocks the pull. The test encodes the bug as correct.

Fix: allow status-only transitions on live rows (permit status in the values dict, or add a dedicated pull_exercise() that sets pulled + purges the affected cache keys), while keeping content columns (payload/grading/explanation) immutable. Add the cache-key-delete step the runbook already names. Wire a review_cli pull command.

H3. A zero-candidate session is persisted and cached as "completed" for the day (NEW; related to the known empty-session trap)
Scenario: On the first GET /session/today of a user's local day, build_session_slots returns [] — possible if the live pool is empty at that moment (fresh deploy, all-pulled during an incident, or grader degraded and zero live deterministic exercises). _build_and_persist_session (sessions/service.py:65-130) does not guard against empty slots: it inserts a daily_sessions row with exercise_list=[], commits it, and get_today_slots caches [] for 36h. get_today_session then returns completed=True with no exercises. The user is locked into an empty, "completed" day even after content is restored, because both the DB row and the cache now say empty.

Why tests missed it: tests always seed a non-empty pool before fetching a session, so the zero-candidate branch is never exercised end-to-end.

Fix: if build_session_slots yields [], do not persist or cache; return a transient "no content yet" response (503-ish or an empty session that is not marked completed and not written to daily_sessions), so the next fetch re-tries once content exists. The prompt asked "is it the only such trap?" — this is a live instance of the same class, still present.

MEDIUM
M1. POST /attempts idempotency + one-attempt rule are not concurrency-safe (NEW)
Scenario: Two concurrent POST /attempts for the same exercise (two tabs/devices, or a network-retry that races the original). get_cached (idempotency.py) and store are separate calls with the real work in between; the already_attempted check (attempts/service.py:325-333) is a plain SELECT with no row lock, no advisory lock, and no DB unique constraint (the schema can't have one — partitioned, per D-7). Both requests miss the cache, both pass the attempted-check, both insert an attempts row, and both run _update_streak_and_attempt_count, which does a read-modify-write on user_stats → lost update on total_attempts, and potentially two streak_events rows for the same day.

Why tests missed it: there are zero concurrency tests (grep confirmed) — every attempt test submits sequentially, where the end-of-request store makes replays byte-identical as designed.

Fix: take a short Redis lock (or SET NX reservation on the idempotency key at the start of the request) so concurrent duplicates serialize; or a Postgres advisory lock on (user_id, exercise_id, session_date) around the attempted-check-through-insert. The client button-disable mitigates the common double-click but not multi-tab/retry.

M2. D-8's "stats job dedupes" is false — nothing dedupes duplicate attempts (NEW)
Scenario: D-8 accepts that "a replay after Redis loss can duplicate; stats job dedupes." But compute_exercise_stats (percentiles.py:17-34) does count(*) / count(*) FILTER (WHERE is_correct) grouped by exercise with no dedup on (user_id, exercise_id, session_date). And user_stats.total_attempts/total_correct are incremented in the request path and never recomputed. So any duplicate (from M1, or Redis loss + replay) permanently inflates solve-rate n, per-user totals, and accuracy. The documented safety net doesn't exist.

Fix: make the aggregation dedupe to one row per (user_id, exercise_id, exercise_version, session_date) (e.g. DISTINCT ON picking the earliest graded attempt) before counting; and/or add the reservation in M1 so duplicates never land.

M3. Timezone change can silently reset a streak; the promised reconciliation job is a placeholder (NEW)
Scenario: docs/05 §3 promises "Changing timezone never retroactively breaks a streak (reconciliation job handles the boundary day)." update_me (users/service.py:63-86) just writes the new timezone. streak_recon.py is a 1-line placeholder. A westward change (e.g. Asia/Kiritimati UTC+14 → Pacific/Midway UTC-11) can make local_date_for(new_tz) earlier than last_active_local_date; the next submit then fails both the == today and == today-1 checks in _update_streak_and_attempt_count (attempts/service.py:193-206) and resets the streak to 1. Streaks are the "retention crown jewel."

Why tests missed it: streak tests hold timezone fixed.

Fix: implement streak_recon (or inline logic in update_me) that, on a timezone change, recomputes/repairs last_active_local_date and writes a streak_events row with event='repaired' (the schema already reserves that value). At minimum, don't let a tz edit move the boundary backward past an already-counted day.

M4. Partition cron can't self-recover once a month is missed (NEW; the risk is flagged in docs/04, the handling isn't built)
Scenario: The monthly partition job is missed (which is guaranteed today per H1, but true generally). Attempts for the new month land in attempts_default. When ensure_next_month_attempts_partition (partitions.py:22-38) later runs, CREATE TABLE ... PARTITION OF attempts FOR VALUES FROM (...) fails because Postgres refuses to create a range partition that overlaps rows already sitting in the DEFAULT partition. docs/04 explicitly warns "move them out BEFORE creating the overlapping monthly partition or the create fails" — but the job never drains attempts_default (the count_attempts_default_rows helper exists but is never called), and it only ever creates next month, so a two-month gap can't be closed.

Fix: before creating a partition, detect/drain overlapping attempts_default rows (create the target partition on a temp, move rows, attach), and loop from the last existing partition up to next month so multi-month gaps recover. Add the "alert if attempts_default has rows" check (docs/04) somewhere that actually runs.

M5. Seed content ships straight to status="live", bypassing every gate and the trust invariant (NEW)
Scenario: seed_e2e.py and seed_summarize_exercises.py insert exercises with status="live", human_reviewed=True directly — no sandbox, no review CLI, hand-written answer keys. For summarize this is by design (no execution oracle). But seed_e2e.py also inserts deterministic spot_the_bug/trace exercises live with hand-asserted correct_lines/correct_choice_id that were never proven by execution — the exact thing invariant #1 forbids. It's labeled "test-only," but it writes to whatever DATABASE_URL points at, and nothing prevents running it against a shared/beta DB. (Also minor: the trace seed uses concepts=["list-indexing"], which isn't in the taxonomy, so it pollutes user_concept_state and the skill graph with an unknown concept.)

Fix: gate seed insertion so non-seed_handauthored/unverified content can't be live outside an explicit dev flag; or insert seeds as in_review and require an approve step. Validate concepts against taxonomy on any insert path.

M6. Taxonomy concepts that require forbidden constructs are un-generatable, and the failure is invisible (KNOWN for open(), NEW for the observability gap)
Scenario: The sampler picks concepts uniformly, but the static gate (static_gate.py:39) forbids open outright, so resource-leak-unclosed-file (D-46 noted this) can never produce a candidate — every one of its 3 attempts fails and the concept gets zero exercises. context-manager-misuse and encoding-decoding-mismatch are similarly starved of their most natural vehicle (open()), and timezone-naive-vs-aware loses .now()/.utcnow() (forbidden attr calls). The deeper problem is observability: BatchReport.log_summary (orchestrator.py:44-56) prints only len(spec_exhausted), not a per-concept breakdown, so a permanently-uncoverable concept looks like generic rejection noise. M8's coverage report would eventually show the hole but not explain it.

Fix: either mark structurally-impossible concepts unsamplable (a requires_forbidden flag in taxonomy) or carve narrow allowances (e.g. permit open() for the resource-leak concept specifically). Add per-concept survival counts to BatchReport so zero-yield concepts surface immediately.

M7. Static gate's nondeterminism screen misses set()/frozenset() constructors (NEW, low-ish)
Scenario: The gate rejects ast.Set/ast.SetComp literals but not set(...)/frozenset(...) calls. Code like for x in set(items): print(x) passes static. Iteration order of a set of strings is hash-randomized (the sandbox doesn't pin PYTHONHASHSEED), so it's caught by the double-run determinism check — usually. A set of small ints iterates deterministically across runs (int hashes aren't randomized), so it passes both gates yet the "correct output" depends on CPython set internals a human reader can't be expected to reproduce. Narrow, but it's a trace-answer correctness risk.

Fix: also flag set(/frozenset( calls in the static gate, and/or set PYTHONHASHSEED=0... actually the opposite — leave hashing randomized so the double-run catches string-set nondeterminism, and add the constructor to the static screen to close the int-set gap.

M8. Live GitHub client secret and OpenAI key sit in plaintext in docker-compose.override.yml (NEW — not a git leak, but a real credential exposure)
Scenario: docker-compose.override.yml contains a real OPENAI_API_KEY (sk-proj-…) and a real GitHub OAuth client secret (1b901…). I verified the file is untracked and gitignored (git ls-files/cat-file confirm it's not in HEAD), so D-43's "never committed" claim holds. But these are live secrets in cleartext on disk; a stray git add -f, a backup, an IDE sync, or sharing the workspace exposes them. The GitHub client secret in particular is a production OAuth app credential.

Fix: rotate both secrets now (assume the OpenAI key and GitHub secret are burned — they're visible in plaintext), move them to a real secrets manager / an untracked .env that's .env.*-ignored, and confirm no history/backup ever captured them.

LOW
Refresh rotation race (NEW): rotate_refresh_token (auth/service.py:127-172) reads the token row without FOR UPDATE; two concurrent refreshes with the same cookie can both pass the rotated_at is None check and issue two valid successors. Rare (refresh is infrequent), reuse-detection is alert-only per D-4. Add with_for_update() on the row read.
X-Forwarded-For spoofing on the pre-auth IP rate limit (NEW): _client_ip (auth/router.py:40-44) trusts the leftmost X-Forwarded-For value, which is client-controlled. An attacker rotating the header bypasses the 10/min per-IP auth limit entirely. Fine if a trusted proxy overwrites XFF, but the code doesn't enforce trusting only the proxy hop. Document the required proxy config or take the rightmost/request.client.host behind a known proxy.
Dispute attempt_id not ownership-checked; uniqueness is racy (NEW): create_dispute (disputes/service.py) stores any attempt_id the client sends (soft link, not validated to belong to the user), and enforces one-open-per-version with a SELECT-then-INSERT (no unique constraint) so two concurrent posts can both insert. Low impact (report metadata), but worth a partial unique index on open disputes.
_diff_changed_lines string concatenation without a separator (NOTED, not a bug): buggy_code + test_code with no newline could merge lines, but that only causes a false reject (syntax error → gate fails), never a false accept, and D-46's trailing-newline constraint covers it. No change needed; just be aware the gate leans on the generator honoring trailing newlines.
Things I checked and believe are SOUND
Injection hardening (invariant 6): the grader never emits a score, only classifies against a closed allowlist, and _score_from_response (rubric.py:179-200) filters to literal rubric members. A fully-obeyed injection can't fabricate a hit. Answer text is angle-bracket-escaped and walled in <student_answer>. Solid.
Sandbox isolation (invariant 7): --network=none, --read-only, --cap-drop=ALL, --pids-limit, memory/cpu caps, non-inherited env, python -I -B, code mounted read-only, double-run determinism. I couldn't find an escape or a nondeterminism leak that survives the double-run.
Answer-key leak boundary (invariant 2): session and attempt serialization copy named fields via strict (extra="forbid") Pydantic models; grading/explanation JSONB are never dumped wholesale; the trace misconception tag is explicitly dropped from the payload. The reveal only appears after a graded attempt exists.
JWT verify: exact-header match (no alg:none), exact-claim-set match, compare_digest, multi-secret rotation. Clean.
Trust guarantee for the bug location: twin-snippet (buggy+test fails w/ AssertionError, fixed+test passes) + bug_lines == actual diff is genuinely execution-proven. Note the reason_id is validated by the LLM reasons gate + human review, not by execution — inherent to the design (docs/01), not a regression, but worth remembering it's the softest part of an otherwise execution-anchored key.
What I'd run to confirm the uncertain ones
H1/H3: boot the tracked docker-compose.yml (no override), submit a summarize attempt, and watch it hang in grading_pending with the client polling forever; then empty the live pool and hit /session/today to see the cached empty "completed" day.
M1/M2: fire two asyncio.gather'd POST /attempts with the same Idempotency-Key at one exercise and assert two attempts rows + total_attempts += 2.
M4: let attempts land in attempts_default, then call ensure_next_month_attempts_partition for the overlapping month and confirm the CREATE TABLE raises.
M6: run python -m pipeline.orchestrator --n 100 against a real generator and grep spec_exhausted for resource-leak-unclosed-file yield (expect 0).
The two I'd gate a public beta on are H1 (features silently dead in prod) and H2 (can't pull a bad exercise — the one incident this product cannot afford to fumble). Neither is a design flaw; both are "the wiring for a shipped feature was never connected," which is precisely the class the milestone tests are structurally blind to.