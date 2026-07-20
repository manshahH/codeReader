import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icons/icon-192.png', 'icons/icon-512.png'],
      workbox: {
        // D-114: the API is same-origin in production (vercel.json rewrites
        // /v1/* to the backend). /v1/auth/github/start is therefore a
        // same-origin top-level navigation, and workbox's default
        // navigateFallback would answer it with the SPA shell -- OAuth would
        // never leave the page. Hand every /v1/* request to the network.
        navigateFallbackDenylist: [/^\/v1\//],
      },
      manifest: {
        name: 'Reedkode',
        short_name: 'Reedkode',
        description: 'Daily code-reading practice: trace, spot the bug, summarize.',
        start_url: '/',
        display: 'standalone',
        background_color: '#FAFAF7',
        theme_color: '#1E40AF',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          {
            src: 'icons/icon-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    // Fail loudly if 5173 is taken instead of silently falling back to 5174:
    // Playwright's webServer url-check would otherwise succeed against the OLD
    // server still on 5173 and the suite would test stale bytes.
    strictPort: true,
  },
});
