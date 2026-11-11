import js from "@eslint/js";
import { defineConfig, globalIgnores } from "eslint/config";
import globals from "globals";
import tseslint from "typescript-eslint";

export default defineConfig([
  globalIgnores(["dist/", "public/mediapipe/", "public/models/", "coverage/"]),
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    rules: {
      // An argument a function must accept but doesn't use is named _like_this.
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    },
  },
  {
    files: ["src/**/*.ts"],
    languageOptions: { globals: globals.browser },
  },
  {
    files: ["scripts/**/*.mjs", "tests/**/*.ts", "*.config.{js,ts}"],
    languageOptions: { globals: globals.node },
  },
]);
