import React from 'react';
import ReactDOM from 'react-dom/client';

import './styles.css';

function App() {
  return (
    <main className='min-h-screen bg-neutral-950 px-6 py-10 text-neutral-50'>
      <section className='mx-auto max-w-3xl'>
        <p className='text-sm font-medium uppercase tracking-wide text-neutral-400'>M0 scaffold</p>
        <h1 className='mt-4 text-4xl font-semibold tracking-normal'>Code Reader</h1>
        <p className='mt-4 max-w-xl text-base leading-7 text-neutral-300'>
          Placeholder shell for the daily code-reading practice app.
        </p>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
