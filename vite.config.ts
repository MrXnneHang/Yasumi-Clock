import { resolve } from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

const host = process.env.TAURI_DEV_HOST;

export default defineConfig({
  clearScreen: false,
  plugins: [react()],
  server: {
    host: host || false,
    port: 1420,
    strictPort: true,
    hmr: host
      ? {
          protocol: 'ws',
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      ignored: ['**/src-tauri/**'],
    },
  },
  envPrefix: ['VITE_', 'TAURI_ENV_*'],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    css: true,
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        restOverlay: resolve(import.meta.dirname, 'rest-overlay.html'),
        settings: resolve(import.meta.dirname, 'settings.html'),
      },
    },
    target:
      process.env.TAURI_ENV_PLATFORM === 'windows' ? 'chrome105' : 'safari13',
    sourcemap: Boolean(process.env.TAURI_ENV_DEBUG),
  },
});
