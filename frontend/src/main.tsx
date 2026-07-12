import React from 'react';
import ReactDOM from 'react-dom/client';

import { App } from './App';
import { ErrorBoundary, FullPageErrorFallback } from './components/ErrorBoundary';
import { initSentry } from './lib/sentry';
import './styles.css';

initSentry();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary fallback={<FullPageErrorFallback />}>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);
