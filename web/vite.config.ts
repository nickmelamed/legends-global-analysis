import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The brand files are supplied, not committed, so they are read from ../brand
// rather than copied into the app.
const brand = fileURLToPath(new URL("../brand", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@brand": brand } },
  server: {
    port: 5173,
    fs: { allow: [".", brand] },
    proxy: { "/api": process.env.API_URL ?? "http://localhost:8000" },
  },
});
