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

python (ruff, ty, flake8-pydantic, vulture, bandit), shell (shellcheck, shfmt),
yaml (yamllint), dockerfile (hadolint), toml (taplo), markdown (markdownlint-cli2),
typescript/js/css (biome, oxlint, semgrep, knip, jscpd), json (jaq/biome)

## configuration

after `plankton init`, hook behavior is configured via `.claude/hooks/config.json`:

- `languages` -- enable/disable per-language linting
- `exclusions` -- paths to skip for security linters (vulture, bandit)
- `subprocess.model` -- claude model for fix delegation (default: "sonnet")
- `subprocess.timeout` -- timeout in seconds (default: 300)
- `phases.auto_format` -- enable/disable Phase 1 auto-formatting
- `phases.subprocess_delegation` -- enable/disable Phase 3 fix delegation

settings.json supports JSONC (JSON with comments).

## license

MIT
