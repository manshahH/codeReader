# Ops Incident & UI Refresh Report - July 2026

This document summarizes recent UI enhancements and a backend debugging investigation regarding transient "Something went wrong" errors. It is intended to help other team members understand the changes being pushed to the repository and the root causes of reported live issues.

## 1. UI Enhancements (Frontend)

We implemented several requested aesthetic and layout changes to the frontend to make the design feel more premium and robust:
- **Login Screen (`Login.tsx`)**: Removed the placeholder "01 02 03" header text to clean up the layout.
- **Review Screen (`Review.tsx`)**: Completely overhauled the layout to a dual-pane, side-by-side design. Code blocks now appear fixed on the left side of the screen, while explanation interactions (Trace Tables, Predict the Fix answers) and feedback scroll natively on the right. Added an interactive `SessionProgressRail` to jump between exercises efficiently.
- **Dashboard & Profile (`Dashboard.tsx`, `Profile.tsx`)**: Addressed layout padding and alignment to match the new, polished design aesthetics (glassmorphism/spacing).

## 2. Debugging Investigation: "Something went wrong" & "Couldn't load..."

We investigated two user-reported errors occurring in production (hosted on Neon/Vercel):

### Symptom A: "Couldn't load..." on the Profile page
Users reported seeing "Couldn't load stats" / "Couldn't load activity" uniformly across the Profile page while their Dashboard session card loaded fine.

**Investigation & Findings:**
- **Cause**: This was identified as a **token refresh race condition**. The Profile page mounts and immediately fires 5 concurrent API calls (stats, concepts, sessions, activity, accuracy).
- **Trigger**: When the access token is expired, `api.ts` intercepts these to request a refresh token. If the backend's `/v1/auth/refresh` endpoint times out (due to Neon DB connection pooling limits hitting their free-tier ceiling under load), all 5 concurrent calls fail simultaneously with a 401 error.
- **Resolution**: No immediate code changes required. The app handles this gracefully by showing a fallback UI section by section (`usePanel` hook). A simple page reload resolves it. When scaling, upgrading the Neon tier to increase the connection pool size will permanently resolve these timeouts.

### Symptom B: "Something went wrong" during a Session (User: abdullahirfann)
A user experienced a hard crash ("Something went wrong" fallback UI) during an active session on the specific exercise `886a7841`.

**Investigation & Findings:**
- **Initial Theory**: We suspected the exercise contained malformed LLM JSON data breaking the strict Pydantic models in `build_reveal` (`grading.py`).
- **Audit Steps Taken**:
  1. Ran pipeline data schema validation across all 109 production exercises.
  2. Wrote a simulator script that ran the exact `build_reveal` function against every row in the DB.
  3. Ran a trace on the specific user's session and attempt history.
- **Actual Root Cause**: The data for all 109 exercises passed strictly. The crash occurred because the user attempted to submit an answer exactly when a transient DB timeout occurred. The backend threw a 403 `exercise_not_in_session` exception because it couldn't retrieve the session lock/slot in time. The frontend `api.ts` fell through to the generic "Something went wrong." catch-all because 403s on that path lack a `{error: ...}` JSON body.
- **Resolution**: The exercise data is perfectly healthy. No DB rows were deleted or altered. The user can simply re-open the app and continue their session seamlessly.

## 3. Environment Variables (Local vs Prod)

We verified that the discrepancies between the local developer `.env` and the production Vercel/Neon variables are intentional and correct:
- **Databases**: Local connects to a local postgres instance; Prod connects to Neon pooler.
- **URIs**: Local uses `http://localhost:5173`; Prod uses `https://codereader-eight.vercel.app`.
- **Secrets**: Local uses dummy values (e.g. `dev-jwt-secret...`); Prod uses cryptographic keys. 
This prevents local development from interacting with real user data or leaking keys.
