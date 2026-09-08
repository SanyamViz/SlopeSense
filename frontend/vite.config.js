import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "inject-risk-api-base",
      transformIndexHtml(html) {
        const base = process.env.RISK_API_BASE || "";
        return html.replace("__RISK_API_BASE__", base);
      },
    },
  ],
  server: {
    port: 5173,
    host: true,
  },
});