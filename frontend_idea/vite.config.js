import { defineConfig } from 'vite';

// The Modda API (python -m modda serve) runs on :8080. Every backend path is proxied to it in development,
// so the page talks to the same origin and no CORS setup is needed.
const API = process.env.MODDA_API_URL || 'http://localhost:8080';
const paths = ['/ask', '/health', '/model', '/chunks', '/articles', '/documents'];

export default defineConfig({
  server: {
    port: 5174,
    proxy: Object.fromEntries(paths.map((p) => [p, { target: API, changeOrigin: true }])),
  },
  preview: { proxy: Object.fromEntries(paths.map((p) => [p, { target: API, changeOrigin: true }])) },
  build: { target: 'es2020', chunkSizeWarningLimit: 900, sourcemap: false },
});
