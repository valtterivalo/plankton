#!/bin/bash
# sync_embedded.sh - copy hook scripts from repo source of truth to embedded package data
#
# Run this after modifying any .claude/hooks/*.sh script to keep the installer
# package in sync with the upstream hooks.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS_SRC="${REPO_ROOT}/.claude/hooks"
HOOKS_DST="${REPO_ROOT}/installer/src/plankton_hooks/_embedded/hooks"

SCRIPTS=(
  "multi_linter.sh"
  "protect_linter_configs.sh"
  "enforce_package_managers.sh"
  "stop_config_guardian.sh"
  "approve_configs.sh"
)

for script in "${SCRIPTS[@]}"; do
  if [[ -f "${HOOKS_SRC}/${script}" ]]; then
    cp "${HOOKS_SRC}/${script}" "${HOOKS_DST}/${script}"
    echo "synced ${script}"
  else
    echo "warning: ${HOOKS_SRC}/${script} not found" >&2
  fi
done

echo "done."
