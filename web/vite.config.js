import { defineConfig } from 'vite';

// During development the FastAPI server runs on :8080; /ask and /health are proxied to it.
export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/ask': 'http://localhost:8080',
      '/health': 'http://localhost:8080',
    },
  },
  build: { target: 'es2020', chunkSizeWarningLimit: 900 },
});
