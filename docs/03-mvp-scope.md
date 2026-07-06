# 03 : MVP Scope

Cut rule: ship anything whose absence breaks trust (wrong answers, lost
streaks, leaked answer keys); defer anything whose absence just means smaller.
Where a cheap decision now avoids a painful migration, build the seam, not the
feature.

## One line
Python only; spot_the_bug + trace + summarize; daily session with streaks;
GitHub login; ~200 validated exercises; web SPA (mobile-responsive, PWA if
cheap); one region, free tier only, no payments, no teams, no native apps.

## In
- Auth: GitHub OAuth + PKCE + single-use state; 15-min JWT + rotating refresh
  cookie. Reuse detection = log + alert only (family kill post-MVP). Seam:
  users + auth_identities split from day one.
- Data: one Postgres, no replicas. Seam: attempts created partitioned anyway.
  Redis for cache/limits/idempotency/queue. Full schema: db/schema.sql,
  rationale in docs/04-database.md.
- Session: built on request (no nightly pre-builder), persisted to
  daily_sessions (Redis flush must not resample), cached in Redis for the day.
- Grading: deterministic in-process sync; summarize graded INLINE with 6s
  timeout behind one internal grade_rubric() seam (queue+WebSocket swap later
  touches one call site). Timeout -> grading_pending + cron retry + poll.
  Streak counts even while pending (product decision, contract-level).
- Streaks: user-local tz, transactional with first attempt of local day,
  streak_events audit rows always.
- Idempotency-Key on POST /attempts (Redis 24h).
- Content: pipeline per docs/01, Python only, three types, run as scripts/cron.
  Twin-snippet invariant and double-run determinism are NOT deferrable.
  Sandbox: Docker --network=none on a SEPARATE cheap VM (machine boundary
  kept; gVisor/Firecracker deferred because MVP executes only
  pipeline-generated code, never user code). 100% human review of the launch
  200 via review CLI. Dispute button -> disputes table + operator email; pull
  is manual.
- Product surface: login, onboarding (level pick), today's session, per-answer
  reveal + percentile (hidden until n>=30), profile (streak, accuracy,
  weakest concepts), dispute. Attempt events also appended as JSONL to S3 from
  day one (10 lines of code, buys the full history).
- API: docs/05-api-contract.md exactly. Note: NO standalone GET /exercises;
  the session is the only content channel (anti-scraping + enforceable
  "in your session" rule).

## Security (MVP-sufficient, none skippable)
1. Answer-key leakage: explicit response schemas (allowlist serialization) +
   CI test that serializes a session and asserts no grading/explanation keys.
2. OAuth correct as above; GitHub token encrypted at rest, never to client.
3. Rate limits (Redis): 60/min default, 10/min attempts, 10/min per-IP auth.
4. Prompt-injection hardening on the summarize grader: delimited data channel,
   strict JSON schema, no tools, invalid -> discard + retry.
5. Sandbox VM: no DB creds, no egress.
6. Baseline: TLS (Caddy), secrets via env from a manager, SameSite=Lax + CORS
   locked to app origin, dependency audit in CI, daily backups with ONE TESTED
   RESTORE BEFORE LAUNCH.

Deferred safely: WAF, RLS (no tenants), SSO, Stripe, family kill, audit log
beyond auth + streaks.

## Performance (MVP-sufficient)
Targets: p95 300ms session fetch and deterministic submit, 6s summarize,
headroom at 5k DAU (~25k attempts/day, trivial for Postgres).
Topology: 2 small API instances behind an LB (deploys/crashes, not load), 1
managed Postgres, 1 managed Redis, 1 sandbox VM. ~$60-120/mo.
Rules kept even at MVP because they cost nothing: stateless API, precomputed
user_stats (never GROUP BY attempts at request time), immutable cache headers
on content responses (CDN later = DNS change), the two attempts indexes only.
Monitoring: Sentry, uptime check, p95/error-rate/LLM-failure dashboard, phone
alerts on error spike and disk >80%.

## Explicit deferral list (nothing silently forgotten)
Read replicas; nightly pre-built bundles; CDN; queue + grading workers +
WebSocket push; token family kill; ClickHouse; OSS bug miner; community
submissions; empirical difficulty calibration (data collected from day one,
computed later); auto kill-switch; leagues/leaderboards; teams + RLS +
per-tenant keys; payments; native apps; multi-provider auth/SSO; notification
infrastructure (MVP: weekly recap email cron + PWA push if free);
gVisor/Firecracker; multi-region. Each has a seam already built.

## Build order (weeks, overlapping)
1. Auth + users + skeleton API
2. Sandbox VM + pipeline for STB and trace; start generating/reviewing the 200
   (the real launch risk lives here)
3. Session serve + deterministic grading + attempts + streaks + stats
4. Summarize inline grading + injection hardening
5. UI polish, disputes, percentile job, S3 event log, backups + restore drill,
   rate limits, CI leak test
6. Private beta (20-30 devs); watch dispute rate and D7 retention before any
   public launch
