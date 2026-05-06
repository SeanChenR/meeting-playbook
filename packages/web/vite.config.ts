import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const GATEWAY_URL = process.env.GATEWAY_URL ?? "http://localhost:3001";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": {
        target: GATEWAY_URL,
        changeOrigin: true,
        ws: true, // forward WebSocket upgrades; needed from Slice 6 onward
      },
    },
  },
});
