import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://localhost:8200",
        changeOrigin: true,
        timeout: 0,
        proxyTimeout: 0,
        rewrite: (p) => p.replace(/^\/api/, ""),
        configure(proxy) {
          let warned = false;
          proxy.on("error", (err) => {
            if (warned) return;
            warned = true;
            console.warn(
              `\n[vite] API proxy (→ http://localhost:8200) error: ${err.message}\n` +
                "    Start the API in another terminal:  mise run api\n" +
                "    Or bring up the full stack:        mise run dev\n",
            );
          });
        },
      },
    },
  },
});
