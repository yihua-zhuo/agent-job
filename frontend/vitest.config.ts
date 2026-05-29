import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    env: {
      NEXT_PUBLIC_AUTH_KEY: "0123456789abcdef0123456789abcdef",
    },
    include: ["src/**/*.test.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json"],
      thresholds: {
        branches: 70,
        functions: 70,
        lines: 70,
      },
    },
  },
});
