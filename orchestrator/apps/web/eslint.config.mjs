import js from "@eslint/js"
import tseslint from "@typescript-eslint/eslint-plugin"
import tsParser from "@typescript-eslint/parser"
import next from "@next/eslint-plugin-next"
import globals from "globals"
import { fileURLToPath } from "node:url"
import { dirname } from "node:path"
import { FlatCompat } from "@eslint/eslintrc"

const __dirname = dirname(fileURLToPath(new URL(".", import.meta.url)))
const compat = new FlatCompat({ baseDirectory: __dirname })

export default [
  {
    ignores: ["node_modules", ".next", "dist"]
  },
  js.configs.recommended,
  ...compat.extends("eslint-config-next/core-web-vitals"),
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        project: "./tsconfig.json",
        tsconfigRootDir: __dirname
      },
      globals: {
        ...globals.browser,
        ...globals.node
      }
    },
    plugins: {
      "@typescript-eslint": tseslint,
      next
    },
    rules: {
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-misused-promises": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "next/no-html-link-for-pages": "off"
    }
  }
]
