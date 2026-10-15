import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Local `uvicorn r2s_web.app:app --app-dir src --port 8000` listens on the host,
// so the default target is loopback. `compose.dev.yml` sets VITE_API_PROXY=http://api:8000
// because inside the compose network the API resolves by service name.
// Setting VITE_API_URL in the browser bypasses the proxy and then requires CORS.
const apiProxy = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";

// Vite rejects requests whose Host header is not an allowed host. When the dev
// server sits behind a reverse proxy (the contest demo gateway in
// `compose.demo.yml`), the proxy forwards the public hostname, so that host
// must be allowlisted explicitly. Unset in `compose.dev.yml`, so direct browser
// access behaves exactly as before.
const allowedHosts = process.env.VITE_ALLOWED_HOSTS?.split(",")
  .map((host) => host.trim())
  .filter(Boolean);

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    ...(allowedHosts?.length ? { allowedHosts } : {}),
    proxy: {
      "/api": {
        target: apiProxy,
        changeOrigin: true,
      },
    },
  },
});