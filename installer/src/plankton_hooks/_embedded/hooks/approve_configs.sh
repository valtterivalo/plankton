#!/bin/bash
# approve_configs.sh - Create guard file for stop hook approval
#
# Usage: approve_configs.sh <ppid> <file1> [file2] ...
#
# Creates a JSON guard file with content hashes for each approved file.
# The stop hook checks this file to avoid re-prompting for the same content.
#
# Guard file format:
# {
#   "approved_at": "2026-01-04T20:00:00Z",
#   "files": {
#     ".yamllint": "sha256:abc123...",
#     ".flake8": "sha256:def456..."
#   }
# }

set -euo pipefail

# portable sha256 - macOS ships shasum, linux ships sha256sum
if command -v sha256sum >/dev/null 2>&1; then
  sha256() { sha256sum "$1" | cut -d' ' -f1; }
elif command -v shasum >/dev/null 2>&1; then
  sha256() { shasum -a 256 "$1" | cut -d' ' -f1; }
else
  echo "error: neither sha256sum nor shasum found" >&2
  exit 1
fi

if [[ $# -lt 2 ]]; then
  echo "Usage: approve_configs.sh <ppid> <file1> [file2] ..." >&2
  exit 1
fi

ppid="$1"
shift

guard_file="${TMPDIR:-/tmp}/stop_hook_approved_${ppid}.json"

# Build JSON with file hashes (using jaq for safe construction)
json='{"approved_at":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","files":{}}'

for file in "$@"; do
  [[ ! -f "${file}" ]] && continue
  hash="sha256:$(sha256 "${file}")"
  json=$(jaq -n --arg f "${file}" --arg h "${hash}" --argjson base "${json}" \
    '$base | .files[$f] = $h')
done

echo "${json}" > "${guard_file}"

echo "Guard file created: ${guard_file}"
