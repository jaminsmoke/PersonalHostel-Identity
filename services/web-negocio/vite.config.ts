import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 8083,
    proxy: {
      "/v1": "http://localhost:8082",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});