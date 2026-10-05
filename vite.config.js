import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O front chama /api/v1/...; em desenvolvimento (npm run dev) e no preview (npm run preview)
// o Vite repassa essas chamadas ao backend, então não há problema de CORS.
const proxy = {
  "/api": {
    target: process.env.SMI_API_TARGET ?? "http://127.0.0.1:8000",
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: { proxy },
  preview: { proxy },
});
