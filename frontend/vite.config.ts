import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Needed for file watching inside Docker on macOS/Windows
    watch: { usePolling: true },
    // Used only when running `npm run dev` without Nginx
    proxy: {
      "/api": process.env.VITE_API_TARGET ?? "http://localhost:8000",
      // Demo panel: availability switches of the external-service mocks
      "/mock/admin": process.env.VITE_MOCKS_TARGET ?? "http://localhost:8001",
    },
  },
});
