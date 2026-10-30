/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const appName = env.VITE_EVENT_NAME || 'Conférence';

  return {
    plugins: [
      react(),
      tailwindcss(),
      VitePWA({
        registerType: 'autoUpdate',
        injectRegister: 'script',
        includeAssets: ['favicon.svg', 'apple-touch-icon.png', 'theme-init.js'],
        manifest: {
          name: `${appName} — Assistant`,
          short_name: appName,
          description: `Assistant conversationnel de ${appName} : speakers, programme, partenaires.`,
          lang: 'fr',
          start_url: '/',
          scope: '/',
          display: 'standalone',
          orientation: 'portrait',
          background_color: '#f7f6f1',
          theme_color: '#1f3d33',
          icons: [
            { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
            { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
            {
              src: '/icons/icon-maskable-512.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'maskable',
            },
          ],
        },
        workbox: {
          navigateFallbackDenylist: [/^\/api\//],
          // Polices : seuls les sous-ensembles latins sont pré-cachés (les autres ne sont
          // téléchargés par le navigateur que si la page contient ces caractères).
          globPatterns: ['**/*.{js,css,html,svg,png}', '**/inter-latin-*.woff2'],
          runtimeCaching: [
            {
              urlPattern: ({ url }) => url.pathname.startsWith('/images/'),
              handler: 'StaleWhileRevalidate',
              options: {
                cacheName: 'images',
                expiration: { maxEntries: 200, maxAgeSeconds: 7 * 24 * 3600 },
              },
            },
          ],
        },
      }),
    ],
    server: {
      proxy: {
        '/api': { target: env.VITE_DEV_API_PROXY || 'http://127.0.0.1:5000', changeOrigin: true },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      restoreMocks: true,
    },
  };
});
