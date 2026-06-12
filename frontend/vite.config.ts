import { defineConfig } from "vite";

// Dev: el frontend (5173) proxea al backend local (8000) → mismo origen, sin CORS.
export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/ws": { target: "ws://localhost:8000", ws: true },
      "/tts": "http://localhost:8000",
      "/chat": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/api": "http://localhost:8000",
    },
  },
});
