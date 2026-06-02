import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Tauri serves the frontend from a fixed dev port and expects a `dist` build.
// https://v2.tauri.app/start/frontend/vite/
export default defineConfig({
  plugins: [react()],
  // Tauri uses Chromium on Windows and WebKit on macOS/Linux.
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    watch: {
      // Don't watch the Rust side; cargo handles that.
      ignored: ["**/src-tauri/**"],
    },
  },
  build: {
    outDir: "dist",
    // Tauri v2 targets modern webviews.
    target: ["es2021", "chrome105", "safari15"],
    sourcemap: false,
  },
});
