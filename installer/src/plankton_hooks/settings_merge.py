"""Idempotent merge of plankton hook entries into a project's .claude/settings.json.

Registers the four plankton hook scripts (protect_linter_configs, enforce_package_managers,
multi_linter, stop_config_guardian) into the target project's Claude Code settings. Each
call is idempotent: existing plankton entries are detected by matching command paths and
are never duplicated. Also provides remove_plankton_hooks for clean uninstall.
"""

import json
import re
from pathlib import Path
from typing import Any, NamedTuple


def _strip_jsonc_comments(text: str) -> str:
    """Strip single-line // comments from JSONC content.

    Claude Code settings files may contain JSONC (JSON with Comments).
    This strips // comments while preserving strings that contain //.

    Args:
        text: Raw JSONC file content.

    Returns:
        JSON-parseable string with comments removed.
    """
    return re.sub(
        r'("(?:[^"\\]|\\.)*")|//[^\n]*',
        lambda m: m.group(1) if m.group(1) else "",
        text,
    )


# -- plankton hook definitions ------------------------------------------------


class _HookDef(NamedTuple):
    """A single plankton hook registration entry.

    Attributes:
        hook_type: Claude Code hook event type (PreToolUse, PostToolUse, Stop).
        matcher: Tool matcher pattern (e.g. "Edit|Write") or empty for all.
        command: Relative path to the hook script.
        timeout: Timeout in seconds for hook execution.
    """

    hook_type: str
    matcher: str
    command: str
    timeout: int


PLANKTON_HOOK_DEFS: list[_HookDef] = [
    _HookDef("PreToolUse", "Edit|Write", ".claude/hooks/protect_linter_configs.sh", 5),
    _HookDef("PreToolUse", "Bash", ".claude/hooks/enforce_package_managers.sh", 5),
    _HookDef("PostToolUse", "Edit|Write", ".claude/hooks/multi_linter.sh", 600),
    _HookDef("Stop", "", ".claude/hooks/stop_config_guardian.sh", 10),
]

PLANKTON_COMMAND_PATHS: set[str] = {h.command for h in PLANKTON_HOOK_DEFS}


def _build_hook_entry(matcher: str, command: str, timeout: int) -> dict[str, Any]:
    """Build a single settings.json hook entry dict.

    Args:
        matcher: Tool matcher pattern (e.g. "Edit|Write", "Bash", or "" for all).
        command: Relative path to the hook script.
        timeout: Timeout in seconds for the hook execution.

    Returns:
        Dict matching the Claude Code settings.json hook entry schema.
    """
    return {
        "matcher": matcher,
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": timeout,
            },
        ],
    }


def _extract_command_paths(entry: dict[str, Any]) -> set[str]:
    """Extract all command paths from a hook entry's hooks array.

    Args:
        entry: A single hook entry dict from settings.json.

    Returns:
        Set of command path strings found in the entry.
    """
    hooks_list: list[dict[str, Any]] = entry.get("hooks", [])
    return {h["command"] for h in hooks_list if "command" in h}


def _has_plankton_command(entry: dict[str, Any]) -> bool:
    """Check whether a hook entry contains any plankton-managed command.

    Args:
        entry: A single hook entry dict from settings.json.

    Returns:
        True if any command path in the entry belongs to plankton.
    """
    return bool(_extract_command_paths(entry) & PLANKTON_COMMAND_PATHS)


def merge_settings(target: Path) -> None:
    """Merge plankton hook entries into the target project's settings.json.

    Reads the existing settings.json (or starts with an empty dict), ensures the
    hooks structure exists, and appends any plankton entries that are not already
    present. Detection is based on command paths: if an existing entry already has
    a hook with the same command, it is skipped.

    If disableAllHooks is True, it is set to False so the hooks actually run.

    Args:
        target: Root directory of the target project (settings.json lives at
                target/.claude/settings.json).
    """
    settings_path = target / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        raw_content = settings_path.read_text(encoding="utf-8")
        settings: dict[str, Any] = json.loads(_strip_jsonc_comments(raw_content))
    else:
        settings = {}

    # -- ensure hooks dict exists
    if "hooks" not in settings:
        settings["hooks"] = {}
    hooks_dict: dict[str, list[dict[str, Any]]] = settings["hooks"]

    # -- merge each plankton hook definition
    for hook_type, matcher, command, timeout in PLANKTON_HOOK_DEFS:
        if hook_type not in hooks_dict:
            hooks_dict[hook_type] = []

        type_entries: list[dict[str, Any]] = hooks_dict[hook_type]

        # check if this command is already registered
        is_already_registered = any(
            command in _extract_command_paths(entry) for entry in type_entries
        )
        if not is_already_registered:
            new_entry = _build_hook_entry(matcher, command, timeout)
            type_entries.append(new_entry)
            print(f"[settings] registered {hook_type} hook: {command}")

    # -- ensure hooks are not globally disabled
    if settings.get("disableAllHooks") is True:
        settings["disableAllHooks"] = False
        print("[settings] re-enabled hooks (disableAllHooks was True)")

    new_content = json.dumps(settings, indent=2) + "\n"
    # Compare against the round-tripped (parsed) version of existing content,
    # not the raw file — raw may contain JSONC comments that would always mismatch.
    if settings_path.exists():
        existing_raw = settings_path.read_text(encoding="utf-8")
        existing_parsed = json.loads(_strip_jsonc_comments(existing_raw))
        existing_canonical = json.dumps(existing_parsed, indent=2) + "\n"
        if existing_canonical == new_content:
            print(f"[settings] {settings_path} unchanged, skipping write")
            return
    settings_path.write_text(new_content, encoding="utf-8")
    print(f"[settings] wrote {settings_path}")


def remove_plankton_hooks(target: Path) -> None:
    """Remove all plankton-managed hook entries from settings.json.

    Scans each hook type array and removes entries whose command paths match
    plankton's known scripts. Empty hook type arrays are cleaned up. Other
    entries in the file are left untouched.

    Args:
        target: Root directory of the target project.
    """
    settings_path = target / ".claude" / "settings.json"

    if not settings_path.exists():
        print("[settings] no settings.json found, nothing to remove")
        return

    raw_content = settings_path.read_text(encoding="utf-8")
    settings: dict[str, Any] = json.loads(_strip_jsonc_comments(raw_content))

    hooks_dict: dict[str, list[dict[str, Any]]] = settings.get("hooks", {})
    if not hooks_dict:
        print("[settings] no hooks section found, nothing to remove")
        return

    hook_types_to_remove: list[str] = []

    for hook_type, entries in hooks_dict.items():
        original_count = len(entries)
        filtered_entries = [e for e in entries if not _has_plankton_command(e)]
        hooks_dict[hook_type] = filtered_entries

        removed_count = original_count - len(filtered_entries)
        if removed_count > 0:
            print(f"[settings] removed {removed_count} plankton entries from {hook_type}")

        if not filtered_entries:
            hook_types_to_remove.append(hook_type)

    for hook_type in hook_types_to_remove:
        del hooks_dict[hook_type]

    # clean up empty hooks dict
    if not hooks_dict:
        del settings["hooks"]

    # if settings is now empty, remove the file entirely
    if not settings:
        settings_path.unlink()
        print(f"[settings] removed empty {settings_path}")
        # remove .claude dir if it's now empty
        claude_dir = settings_path.parent
        if claude_dir.exists() and not any(claude_dir.iterdir()):
            claude_dir.rmdir()
            print(f"[settings] removed empty {claude_dir}")
    else:
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        print(f"[settings] wrote {settings_path}")
