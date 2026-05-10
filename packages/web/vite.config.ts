import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const GATEWAY_URL = process.env.GATEWAY_URL ?? "http://localhost:3001";

// Slice-7 round 2/3: meeting WS closes naturally (server FINs first); Node's
// underlying socket then fires `writeAfterFIN` which surfaces as
// `Error: This socket has been ended by the other party`. http-proxy's own
// `error` event only fires for some of these — others bubble through the
// raw upgrade socket. Filter at every hook + on the raw client/upstream
// sockets exposed by `proxyReqWs` and `open`.
const _BENIGN_PATTERNS = ["socket has been ended", "ECONNRESET", "write after end", "EPIPE"];
const _isBenign = (err: unknown): boolean => {
  const msg = (err as Error | undefined)?.message ?? "";
  return _BENIGN_PATTERNS.some((p) => msg.includes(p));
};
const _swallow = (err: unknown): void => {
  if (_isBenign(err)) return;
  // eslint-disable-next-line no-console
  console.error("[vite proxy]", err);
};

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
        configure: (proxy) => {
          proxy.on("error", _swallow);
          // Each WS upgrade exposes the upstream client request (proxyReqWs)
          // and on `open` the raw upstream socket. Both can fire raw socket
          // errors when the downstream half closes; attach silent error
          // listeners to each so Node doesn't promote them to uncaught.
          proxy.on("proxyReqWs", (proxyReq, _req, socket) => {
            proxyReq.on("error", _swallow);
            socket.on("error", _swallow);
          });
          proxy.on("open", (upstreamSocket) => {
            upstreamSocket.on("error", _swallow);
          });
          proxy.on("close", (_req, socket /* incoming */, _head) => {
            socket?.on?.("error", _swallow);
          });
        },
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
