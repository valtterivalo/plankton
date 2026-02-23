"""Generate .claude/hooks/config.json from language detection results.

Produces a config dict that matches the canonical schema used by the
plankton hook scripts, then writes it to disk. The generated config
drives all downstream linting, formatting, and subprocess delegation.
"""

import json
from pathlib import Path

from plankton_hooks.models import DetectionResult

# -- schema version ------------------------------------------------------------

_CC_TESTED_VERSION = "2.1.50"
_SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"

# -- protected files (always included regardless of detection) -----------------

_PROTECTED_FILES: list[str] = [
    ".markdownlint.jsonc",
    ".markdownlint-cli2.jsonc",
    ".shellcheckrc",
    ".yamllint",
    ".hadolint.yaml",
    ".jscpd.json",
    ".flake8",
    "taplo.toml",
    ".ruff.toml",
    "ty.toml",
    "biome.json",
    ".oxlintrc.json",
    ".semgrep.yml",
    "knip.json",
]

# -- standard exclusions -------------------------------------------------------

_EXCLUSIONS: list[str] = [
    "tests/",
    "docs/",
    ".venv/",
    "scripts/",
    "node_modules/",
    ".git/",
    ".claude/",
]

# -- config builders -----------------------------------------------------------


def _build_languages_block(detection: DetectionResult) -> dict:
    """Build the ``languages`` section of the config.

    Simple languages get a plain boolean. TypeScript gets a nested object
    with extra knobs for biome, semgrep, etc.

    Args:
        detection: Language detection results from the scan phase.

    Returns:
        Dict matching the ``languages`` key in config.json.
    """
    is_python_enabled = detection.is_enabled("python")
    is_shell_enabled = detection.is_enabled("shell")
    is_yaml_enabled = detection.is_enabled("yaml")
    is_json_enabled = detection.is_enabled("json")
    is_toml_enabled = detection.is_enabled("toml")
    is_dockerfile_enabled = detection.is_enabled("dockerfile")
    is_markdown_enabled = detection.is_enabled("markdown")
    is_typescript_enabled = detection.is_enabled("typescript")

    languages: dict = {
        "python": is_python_enabled,
        "shell": is_shell_enabled,
        "yaml": is_yaml_enabled,
        "json": is_json_enabled,
        "toml": is_toml_enabled,
        "dockerfile": is_dockerfile_enabled,
        "markdown": is_markdown_enabled,
    }

    if is_typescript_enabled:
        languages["typescript"] = {
            "enabled": True,
            "js_runtime": "auto",
            "biome_nursery": "warn",
            "biome_unsafe_autofix": False,
            "oxlint_tsgolint": False,
            "tsgo": False,
            "semgrep": True,
            "knip": False,
        }
    else:
        languages["typescript"] = {
            "enabled": False,
            "js_runtime": "auto",
            "biome_nursery": "warn",
            "biome_unsafe_autofix": False,
            "oxlint_tsgolint": False,
            "tsgo": False,
            "semgrep": False,
            "knip": False,
        }

    return languages


def _build_package_managers_block(detection: DetectionResult) -> dict:
    """Build the ``package_managers`` section of the config.

    Sets the primary python/javascript package manager based on detection,
    and always includes the full allowed_subcommands map.

    Args:
        detection: Language detection results from the scan phase.

    Returns:
        Dict matching the ``package_managers`` key in config.json.
    """
    is_python_enabled = detection.is_enabled("python")
    is_typescript_enabled = detection.is_enabled("typescript")

    return {
        "python": "uv" if is_python_enabled else False,
        "javascript": detection.js_package_manager if is_typescript_enabled else False,
        "allowed_subcommands": {
            "npm": ["audit", "view", "pack", "publish", "whoami", "login"],
            "pip": ["download"],
            "yarn": ["audit", "info"],
            "pnpm": ["audit", "info"],
            "poetry": [],
            "pipenv": [],
        },
    }


# -- public API ----------------------------------------------------------------


def generate_config(detection: DetectionResult) -> dict:
    """Produce the full .claude/hooks/config.json content as a dict.

    The returned dict matches the canonical plankton config schema exactly,
    including all top-level keys: languages, protected_files, exclusions,
    phases, subprocess, jscpd, and package_managers.

    Args:
        detection: Language detection results from the scan phase.

    Returns:
        Config dict ready for JSON serialisation.
    """
    return {
        "$schema": _SCHEMA_URI,
        "cc_tested_version": _CC_TESTED_VERSION,
        "_comment": "Claude Code Hooks Configuration - edit this file to customize hook behavior",
        "languages": _build_languages_block(detection),
        "protected_files": list(_PROTECTED_FILES),
        "exclusions": list(_EXCLUSIONS),
        "phases": {
            "auto_format": True,
            "subprocess_delegation": True,
        },
        "subprocess": {
            "timeout": 300,
            "model": "sonnet",
        },
        "jscpd": {
            "session_threshold": 3,
            "scan_dirs": ["src/", "lib/"],
            "advisory_only": True,
        },
        "package_managers": _build_package_managers_block(detection),
    }


def write_config(target: Path, config: dict) -> None:
    """Write the config dict to target/.claude/hooks/config.json.

    Creates the directory tree if it does not exist. Overwrites any
    existing config file without prompting.

    Args:
        target: Root directory of the target project.
        config: Config dict (from generate_config).
    """
    hooks_dir = target / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    config_path = hooks_dir / "config.json"
    config_json = json.dumps(config, indent=2) + "\n"
    config_path.write_text(config_json, encoding="utf-8")

    print(f"wrote config to {config_path}")
