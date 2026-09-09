import { defineConfig } from "vite";

/**
 * GitHub Pages serves the project site from /<repo>/, so the published bundle
 * needs a matching base path. Local dev and the Compose/nginx runtime serve from
 * the root, so the base is only applied when DEPLOY_BASE is provided by CI.
 */
export default defineConfig({
  base: process.env.DEPLOY_BASE ?? "/",
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
