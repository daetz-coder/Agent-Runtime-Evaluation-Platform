import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const apiTarget = process.env.VITE_WIKI_API_BASE || "http://127.0.0.1:8001";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
});
