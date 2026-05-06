import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const GATEWAY_URL = process.env.GATEWAY_URL ?? "http://localhost:3001";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": {
        target: GATEWAY_URL,
        changeOrigin: true,
        ws: true,
      },
    },
    // The page is served via the Bun gateway at :3001, but Vite's HMR socket
    // talks directly to :5173 from the browser. Without clientPort, Vite would
    // try to connect to ws://localhost:3001 (the page origin) which the
    // gateway doesn't proxy for HMR.
    hmr: {
      clientPort: 5173,
    },
  },
});
