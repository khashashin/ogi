import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // New in eslint-plugin-react-hooks 7.1. It flags effects that set state synchronously,
      // mostly dialogs that reset their form when opened and loads that set a loading flag
      // first. Those cost an extra render but aren't bugs; moving them to keyed remounts or
      // derived state is a refactor of its own, so they stay visible as warnings until then.
      'react-hooks/set-state-in-effect': 'warn',
    },
  },
])
