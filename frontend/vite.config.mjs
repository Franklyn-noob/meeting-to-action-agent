import { defineConfig } from "vite";

export default defineConfig({
  server: {
    // Live backend (uvicorn on :8000) during `npm run dev`.
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
