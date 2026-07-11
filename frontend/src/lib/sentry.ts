import * as Sentry from '@sentry/react';

const dsn = import.meta.env.VITE_SENTRY_DSN;

/** No DSN (the common local-dev case) must never break the app. */
export function initSentry(): void {
  if (!dsn) return;

  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
    beforeSend(event) {
      // Never send the access token, the user's answer text, or any code
      // payload -- request bodies carry all three (see lib/api.ts).
      if (event.request) {
        delete event.request.data;
        delete event.request.cookies;
        if (event.request.headers) {
          for (const name of Object.keys(event.request.headers)) {
            if (name.toLowerCase() === 'authorization') delete event.request.headers[name];
          }
        }
      }
      return event;
    },
  });
}
