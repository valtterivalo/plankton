# plankton-hooks

write-time code quality enforcement for Claude Code.

plankton installs PostToolUse/PreToolUse/Stop hooks into your project that
automatically lint, format, and fix code every time Claude edits a file. it
enforces the boy scout rule: if you touch a file, you own all its violations.

## install

```bash
uvx plankton-hooks init --target /path/to/your/project
```

## commands

- `plankton init` -- full installation (hooks, configs, deps, CLAUDE.md)
- `plankton update` -- refresh hooks and config without touching linter configs or deps
- `plankton uninstall` -- remove plankton hooks (leaves linter configs and deps)
- `plankton status` -- show what's installed
- `plankton init --dry-run` -- preview what would be installed

## what it does

- **PostToolUse** (Edit/Write): runs language-specific linters after every file edit.
  auto-formats first, then collects violations and delegates to a subprocess for fixes.
- **PreToolUse** (Edit/Write): blocks modifications to linter config files.
  fix the code, not the rules.
- **PreToolUse** (Bash): enforces preferred package managers (uv for python, bun for js).
- **Stop**: checks for linter config modifications at session end.

## supported languages

python (ruff, ty, flake8-pydantic), shell (shellcheck, shfmt), yaml (yamllint),
dockerfile (hadolint), toml (taplo), markdown (markdownlint-cli2),
typescript/js/css (biome, semgrep), json (jaq/biome)

## license

MIT
