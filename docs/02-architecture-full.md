# 02 : Architecture (Full / End-State)

This is the destination. docs/03-mvp-scope.md is the subset we build first;
every MVP decision leaves a seam pointing here. Scale targets used for sizing:
1M registered, 150k DAU, ~100:1 read:write, spiky daily-habit traffic.

## Topology
```
[Mobile / Web SPA]
      |
 [CDN / Edge]            static assets, immutable exercise content, cached leaderboards
      |
 [Gateway / LB]          TLS, rate limits, WAF
      |
 [Core API xN]           FastAPI modular monolith, stateless
   |        |        |          |
[Postgres] [Redis] [Queue]  [S3: artifacts, bundles, event log]
 primary+   cluster   |
 replicas          [Grading workers] -> LLM APIs
                      |
            [Content pipeline workers] -> LLM APIs
                      |
              [Sandbox executor fleet]   isolated VPC, zero DB access
```

Four deployables only: Core API (modular monolith), content pipeline workers,
sandbox fleet, grading workers. Boundaries drawn where failure domains,
security domains, and scaling curves differ; everything else stays a module.
REST, not GraphQL: read patterns are predictable and must be CDN-cacheable.

## Identity
GitHub OAuth (Authorization Code + PKCE, single-use state in Redis, scope
read:user only). Provider-agnostic tables (users + auth_identities) so
Google/SSO for Teams is a row type, not a migration. Sessions: 15-min JWT
access tokens (sub, plan, team_id, exp only) + opaque rotating refresh tokens,
hashed at rest, per-device rows, reuse detection kills the token family.
Refresh in HttpOnly SameSite=Lax cookie scoped to the refresh endpoint; access
token in memory (web) / keychain (mobile). GitHub tokens AES-GCM encrypted,
never on the request path. Teams repo access is a separate GitHub App install,
never a login scope creep.

## Data
- Postgres: source of truth (see docs/04-database.md). Read replicas for miss
  traffic. attempts partitioned monthly, append-only, minimal indexes;
  per-user aggregates precomputed (user_stats, user_concept_state); nothing
  user-facing aggregates attempts at request time.
- Redis: session bundles, streak hot copy, leaderboard sorted sets, rate
  limits, idempotency, queues (until SQS).
- S3: validation reports, sandbox artifacts, exercise content bundles, JSONL
  attempt event log.
- ClickHouse (phase 2, >10M attempts): analytical copy of the event firehose
  for cohorts, retention, empirical difficulty.

## Read path (the app is read-heavy; strategy per read)
1. Today's session: NIGHTLY PRE-BUILDER assembles per-user bundles (spaced
   repetition + curriculum + boss), grading stripped, into Redis (48h TTL) +
   S3. Morning spike = one Redis GET per user; Postgres nearly idle at 8am.
   Sync fallback path serves <1%.
2. Exercise content: immutable per version -> CDN with
   `Cache-Control: public, max-age=31536000, immutable`; version bump = new
   URL = free invalidation.
3. Leaderboards: Redis sorted sets per (league, week); global boards CDN-cached
   60s; Postgres stores only frozen weekly snapshots.
4. Profile/skill graph: precomputed tables, Redis 5-min cache, replicas on miss.
5. Percentiles: periodic job -> exercise_stats + Redis; never computed live.

Cache law: no cache without a documented owner, TTL, and invalidation trigger.

## Write path
- POST /attempts requires client Idempotency-Key (Redis 24h).
- Deterministic grading: in-process, synchronous, single-digit ms.
- Rubric grading: 202 + queue -> workers -> grading_results -> Redis pub/sub ->
  WebSocket push (any replica can hold the socket), polling fallback, p95 < 4s.
- LLM degradation: monitored; past thresholds, rubric exercises are withheld
  from newly built sessions and pending attempts notify on completion. The app
  never hard-depends on an LLM being up.
- Streaks: user-local timezone, updated transactionally with first attempt of
  the local day, audited transitions, daily reconciliation job for edge cases.

## Content plane
Pipeline per docs/01. Workers autoscale on queue depth in their own
VPC/subnet, no route to user Postgres, write through a narrow internal Content
API. Sandbox fleet: Firecracker/gVisor, --network=none, no IAM beyond one S3
artifact prefix, no DB creds; treats ALL code as hostile (community
submissions make this literal later). Publishing is atomic per version:
Postgres row + CDN bundle together. Teams private-repo mode: per-tenant
encryption keys, per-tenant S3 prefixes, team_id row tags, Postgres RLS as
backstop, CI tests that attempt cross-tenant reads and must fail.

## Security threat list (ranked)
1. Cross-tenant leak of private-repo exercises: RLS + tenant keys + CI
   isolation tests.
2. Sandbox escape: machine boundary, gVisor/Firecracker, credential-free hosts.
3. Answer-key leakage: serializer allowlists + CI leak test on session bundles.
4. Account takeover: PKCE, state, rotation + family kill, encrypted tokens.
5. Corpus scraping: authed content endpoints, rate limits, anomaly alerts.
6. Prompt injection via free-text answers: delimited data channel, strict JSON
   schema output, no tools, out-of-range discarded and retried.
7. Payments: Stripe webhooks signature-verified; entitlements only from the
   subscriptions table; plan claim refreshed on renewal.
8. Baseline: TLS, secrets manager, dependency scanning, WAF, audit log,
   restore-drilled backups.

## Performance budgets and failure order
Budgets: p95 150ms session fetch, 250ms deterministic submit, 4s rubric, <2s
cold mobile load. First cliffs and pre-planned levers:
1. attempts insert contention -> stats aggregation moves from transactional to
   queue consumer (insert becomes single-row); sharding is the distant last
   resort.
2. Leaderboard hot keys -> already sharded per ~30-user league cohort.
3. LLM throughput at evening spike -> worker autoscale + second provider
   fallback, priority-ordered.
4. Morning spike -> absorbed by pre-built bundles; remaining work is JWT
   verify (CPU, add replicas) + Redis GETs.

Single primary region + global CDN indefinitely; multi-region only if a Teams
contract demands residency, and then as a second isolated stack, never
active-active.

## Supporting planes
Notifications (scheduler on next_session_at -> FCM/APNs, teaser from the
user's bundle; transactional email for recaps). Analytics (events -> S3 ->
ClickHouse; calibration jobs close the loop into content). Admin plane
(internal-only app behind SSO: review UI, dispute queue, kill switch that
propagates < 1 min by flipping status + deleting bundle keys). Observability
(traces API->queue->worker under one trace id; four golden alerts: session
fetch p95, attempt insert error rate, grading queue age, per-exercise dispute
rate).
