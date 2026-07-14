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

*   **The Problem:** If GITHUB_REDIRECT_URI is set to the backend domain (https://codereader.fastapicloud.dev/v1/auth/github/callback), GitHub redirects the user there after login. The backend issues a Set-Cookie header for the efresh_token attached to the astapicloud.dev domain (with SameSite=lax and Secure=true). It then redirects the user to the frontend app. When the frontend attempts to call POST /v1/auth/refresh on its own domain (via the proxy), the browser **will not send the cookie** because the domains do not match. The API rejects the request with 401 Unauthorized.
*   **The Fix:** GITHUB_REDIRECT_URI MUST be set to the frontend proxy domain:
    \GITHUB_REDIRECT_URI=https://<frontend-domain>.vercel.app/v1/auth/github/callback\
    This forces the OAuth callback to flow through the Vercel proxy. The backend processes it and sends the Set-Cookie header, but because the browser is interacting with the Vercel domain, it associates the cookie with the frontend domain. Subsequent API calls will successfully include the cookie.

## 4. Background Jobs & Database Connections

When JOBS_ENABLED=true is set, the backend spins up APScheduler in the lifespan event (ackend/app/main.py). This requires a stable database connection.

*   Ensure the Neon Postgres database is using a connection string compatible with syncpg. If you encounter timeouts (e.g., TimeoutError after 30-60 seconds during startup), verify that your connection string (like a Transaction Pooler URL) does not have incompatible parameters. 
*   Because startup can take up to 8-9 minutes on FastAPI Cloud deployments when cold-starting with Jobs, checking the logs prematurely might show old runtime logs. Always wait for the deployment status to hit success before assuming a failure.
