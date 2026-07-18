# FastAPI Cloud Deployment Runbook

This document captures the hard-won lessons from deploying the CodeReader backend to FastAPI Cloud, specifically focusing on how to avoid persistent deployment and authentication failures.

## 1. Directory and Build Configuration

When deploying a sub-directory (like ackend/) to FastAPI Cloud using the CLI, there is a mismatch potential between what you upload and what the cloud builder expects.

*   **The Command:** astapi cloud deploy backend archives the *contents* of the ackend/ folder and uploads them. The root of your uploaded artifact is now the root of your Python project (containing pyproject.toml).
*   **The App Settings:** In the FastAPI Cloud dashboard (or via astapi cloud apps update <APP_ID> --directory .), the App's **Root Directory** setting MUST be set to .. 
    *   *Anti-pattern:* If you set the directory to ackend, the cloud buildpack will attempt to cd backend into the uploaded artifact. Since the artifact *is* the backend folder, the directory doesn't exist. The buildpack will fail to cd, fall back to the root, but the runtime astapi run command will still try to execute from a non-existent ackend directory, failing with Could not find a default file to run, please provide an explicit path.

## 2. Packaging the Entrypoint (pyproject.toml)

FastAPI Cloud uses uv to build a .whl package of your source code during deployment, and then installs that wheel into the runtime container.

If you are using a shim file at the root of your project (e.g., ackend/main.py which re-exports your app to satisfy astapi run auto-discovery), you **must** instruct setuptools to include it in the wheel.

In ackend/pyproject.toml:
\\\	oml
[tool.setuptools]
packages = ['app']
py-modules = ['main'] # CRITICAL: Without this, main.py is excluded from the build!
\\\

If main.py is excluded, it will not exist in the runtime container. astapi run will fail to find it, fall back to searching __init__.py structures, and often fail to boot entirely.

## 3. Cross-Domain OAuth Cookies (Vercel Proxy)

CodeReader's frontend is hosted on Vercel (codereader-eight.vercel.app) and the backend on FastAPI Cloud (codereader.fastapicloud.dev). To bypass CORS issues, the frontend uses a ercel.json rewrite to proxy /v1/* requests to the backend, making them appear same-origin.

This architectural decision heavily impacts OAuth flows:

*   **The Problem:** If GITHUB_REDIRECT_URI is set to the backend domain (https://codereader.fastapicloud.dev/v1/auth/github/callback), GitHub redirects the user there after login. The backend issues a Set-Cookie header for the 
efresh_token attached to the astapicloud.dev domain (with SameSite=lax and Secure=true). It then redirects the user to the frontend app. When the frontend attempts to call POST /v1/auth/refresh on its own domain (via the proxy), the browser **will not send the cookie** because the domains do not match. The API rejects the request with 401 Unauthorized.
*   **The Fix:** GITHUB_REDIRECT_URI MUST be set to the frontend proxy domain:
    \GITHUB_REDIRECT_URI=https://<frontend-domain>.vercel.app/v1/auth/github/callback\
    This forces the OAuth callback to flow through the Vercel proxy. The backend processes it and sends the Set-Cookie header, but because the browser is interacting with the Vercel domain, it associates the cookie with the frontend domain. Subsequent API calls will successfully include the cookie.

## 3b. Local-dev GitHub OAuth (a SECOND OAuth app)

A GitHub OAuth app accepts ONE callback URL. Section 3 pins production's to the
Vercel proxy host, so local dev cannot share it: hitting
`/v1/auth/github/start` locally returns GitHub's
`redirect_uri is not associated with this application`. This is the documented
limit of D-114, and it needs a second, dev-only OAuth app. Do NOT repoint the
production app.

**1. Create it** at <https://github.com/settings/developers> -> New OAuth App.
- Application name: anything, e.g. `CodeReader (local dev)`
- Homepage URL: `http://localhost:5173`
- **Authorization callback URL: `http://localhost:8000/v1/auth/github/callback`**
  This is the BACKEND, not the frontend. Locally there is no same-origin
  rewrite, so the callback must land on the API that will set the cookie.
- Generate a client secret.

**2. Set these in your local `.env`** (or `docker-compose.override.yml`, which
wins over `.env` for the api container, and is gitignored):

```
GITHUB_CLIENT_ID=<the dev app's client id>
GITHUB_CLIENT_SECRET=<the dev app's client secret>
GITHUB_REDIRECT_URI=http://localhost:8000/v1/auth/github/callback
APP_ORIGIN=http://localhost:5173
```

`APP_ORIGIN` is doing two jobs and both matter: it is the CORS allowlist entry
(the SPA on :5173 calling the API on :8000 is cross-origin) and the base for
the post-callback redirect and A2's verification links.

Restart the api container after changing these; Settings is `@lru_cache`d.

**3. Why the refresh cookie still works locally, despite section 3.** Section 3
exists because production's frontend and backend are different REGISTRABLE
DOMAINS, so a cookie set by the backend domain is not sent to the frontend
domain. Locally they are the same host, `localhost`, differing only by PORT, and
**cookies do not include the port in their scope** (RFC 6265: same-origin rules
apply to schemes and hosts, not ports). So the `rt` cookie the backend sets is
sent back on the SPA's `POST /v1/auth/refresh` even though the SPA is served
from :5173. The Vercel rewrite is a production-only requirement, and no local
proxy is needed.

Two things that DO have to line up locally, both already correct in the
committed config: CORS must allow `http://localhost:5173` with
`allow_credentials=true` (it does, from `APP_ORIGIN`), and the SPA must send
`credentials: 'include'` (it does, in `api.ts`).

**4. Verify.** `curl -si localhost:8000/v1/auth/github/start | grep -i location`
should show `redirect_uri=http%3A%2F%2Flocalhost%3A8000%2F...` matching the dev
app's registered callback exactly, including scheme and port.

## 4. Background Jobs & Database Connections

When JOBS_ENABLED=true is set, the backend spins up APScheduler in the lifespan event (ackend/app/main.py). This requires a stable database connection.

*   Ensure the Neon Postgres database is using a connection string compatible with syncpg. If you encounter timeouts (e.g., TimeoutError after 30-60 seconds during startup), verify that your connection string (like a Transaction Pooler URL) does not have incompatible parameters. 
*   Because startup can take up to 8-9 minutes on FastAPI Cloud deployments when cold-starting with Jobs, checking the logs prematurely might show old runtime logs. Always wait for the deployment status to hit success before assuming a failure.

## 5. Pending release: A1 streak safety net (not yet deployed)

A1 is built and merged but NOT deployed; the plan is to build more of Phase A
and ship it as v2. This is the checklist for whenever that release happens.

**Deploy order matters: backend FIRST, then the frontend.** The new frontend
reads `repair_restores_to` from `GET /v1/me/stats`. Against an old backend that
field is absent, and `undefined !== null` is true, so the welcome-back panel
renders with `undefined` in its label ("Restore your undefined-day streak").
Deploying the backend first closes that window entirely. The reverse order is
the only combination that misbehaves: an old frontend against the new backend
simply ignores the two extra fields.

**Environment.** No new REQUIRED variables. The four A1 knobs all have working
defaults in `config.py` and only need setting to override:

    STREAK_FREEZE_START=2        STREAK_FREEZE_MAX=2
    STREAK_FREEZE_EARN_EVERY=10  STREAK_REPAIR_WINDOW_H=48

`ADMIN_METRICS_TOKEN` is the one to actually check. It was already required for
`/admin/metrics`, and it now also gates both new admin streak routes. If it is
unset in production those routes return **404, not 403** (the handler treats an
unconfigured token as "endpoint disabled" rather than confirming the route
exists), so a missing token looks like a missing deploy. Verify it is set before
concluding the routes did not ship.

**No migration.** A1 required no schema change: the `streak_events.event` CHECK
already allowed all five event kinds, the partial unique index
`uq_streak_events_one_transition_per_day` already excludes the new kinds
(`WHERE event IN ('extended','reset')`), and `user_stats.streak_freezes`
already existed. Alembic head is unchanged.

**One post-deploy action, once:**

    POST /admin/streak/grant-initial-freezes  {"local_date": "<today>"}
    Header: X-Admin-Token: <ADMIN_METRICS_TOKEN>

This is the D-118 backfill. Accounts created before A1 sit at
`streak_freezes = 0`, because the starting grant happens at row creation, so
without it every existing soft-launch user waits up to 10 active days for their
first freeze while new signups start with 2. It is idempotent on both the
balance and a ledger marker, so re-running is a no-op reporting
`granted_to: 0` -- including for users who were granted and have since
legitimately spent their freezes. Safe to re-run if you are unsure whether it
ran.

`POST /admin/streak/outage-freeze {"local_date": ...}` is the ops "big red
button" for after an outage. It is a pure ledger write: it spends no balance,
mutates no `current_streak`, and cannot manufacture a streak (D-116). Re-running
it for the same date is also a no-op.
