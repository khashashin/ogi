# Agent Notes

Before running tests, linters, builds, or package-manager commands:
- Determine the correct project root first.
- For Python commands such as `uv` and `pytest`, run from the nearest directory containing `pyproject.toml`.
- For Node commands such as `pnpm`, `npm`, and `vite`, run from the nearest directory containing `package.json`.
- Do not assume the repository root is the package root in this monorepo.
- If a command fails with errors such as `program not found` or `--extra ... has no effect outside of a project`, verify the working directory before changing the command.
