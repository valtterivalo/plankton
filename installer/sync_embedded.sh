#!/bin/bash
# sync_embedded.sh - copy hook scripts and linter configs from repo source of truth
#                    to embedded package data
#
# Run this after modifying any .claude/hooks/*.sh script or linter config file
# to keep the installer package in sync with the upstream sources.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# -- hook scripts --------------------------------------------------------------

HOOKS_SRC="${REPO_ROOT}/.claude/hooks"
HOOKS_DST="${REPO_ROOT}/installer/src/plankton_hooks/_embedded/hooks"

SCRIPTS=(
  "multi_linter.sh"
  "protect_linter_configs.sh"
  "enforce_package_managers.sh"
  "stop_config_guardian.sh"
  "approve_configs.sh"
)

echo "--- syncing hook scripts ---"
for script in "${SCRIPTS[@]}"; do
  if [[ -f "${HOOKS_SRC}/${script}" ]]; then
    cp "${HOOKS_SRC}/${script}" "${HOOKS_DST}/${script}"
    echo "  synced ${script}"
  else
    echo "  warning: ${HOOKS_SRC}/${script} not found" >&2
  fi
done

# -- linter configs ------------------------------------------------------------
# each line: repo_root_file|embedded_relative_path

EMBEDDED_ROOT="${REPO_ROOT}/installer/src/plankton_hooks/_embedded"

echo "--- syncing linter configs ---"

sync_config() {
  local src_file="$1" dst_rel="$2"
  local src_path="${REPO_ROOT}/${src_file}"
  local dst_path="${EMBEDDED_ROOT}/${dst_rel}"

  if [[ -f "${src_path}" ]]; then
    cp "${src_path}" "${dst_path}"
    echo "  synced ${src_file} -> ${dst_rel}"
  else
    echo "  skip: ${src_file} not found at repo root" >&2
  fi
}

sync_config ".ruff.toml"               "configs/python/.ruff.toml"
sync_config "ty.toml"                  "configs/python/ty.toml"
sync_config ".flake8"                  "configs/python/.flake8"
sync_config ".shellcheckrc"            "configs/shell/.shellcheckrc"
sync_config ".yamllint"                "configs/yaml/.yamllint"
sync_config ".hadolint.yaml"           "configs/dockerfile/.hadolint.yaml"
sync_config "taplo.toml"               "configs/toml/taplo.toml"
sync_config ".markdownlint.jsonc"      "configs/markdown/.markdownlint.jsonc"
sync_config ".markdownlint-cli2.jsonc" "configs/markdown/.markdownlint-cli2.jsonc"
sync_config ".jscpd.json"              "configs/general/.jscpd.json"

echo "done."
