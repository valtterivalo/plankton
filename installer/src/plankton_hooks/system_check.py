"""System tool availability checker for the plankton installer.

Verifies that required CLI tools (jaq, uv, bun) are on PATH and reports
the availability of optional per-language linters. Crashes immediately
when a required tool is missing.
"""

import shutil
import sys
from collections.abc import Callable

from plankton_hooks.models import DetectionResult, ToolStatus

# -- column widths for stdout table ------------------------------------------------

_COL_TOOL = 22
_COL_KIND = 10
_COL_STATUS = 9
_COL_HINT = 0  # hint column is unbounded


def _has_tool(name: str) -> bool:
    """Return whether *name* resolves to an executable on PATH.

    Args:
        name: CLI executable name (e.g. "ruff", "shellcheck").

    Returns:
        True if shutil.which finds the tool, False otherwise.
    """
    return shutil.which(name) is not None


def _tool(
    name: str,
    *,
    is_required: bool,
    install_hint: str,
) -> ToolStatus:
    """Build a ToolStatus for a single CLI tool.

    Args:
        name: Executable name.
        is_required: Whether the installer must abort if missing.
        install_hint: Human-readable install instruction.

    Returns:
        Frozen ToolStatus dataclass.
    """
    return ToolStatus(
        name=name,
        is_required=is_required,
        is_available=_has_tool(name),
        install_hint=install_hint,
    )


# -- optional tool sets per language -----------------------------------------------


def _python_tools() -> list[ToolStatus]:
    """Optional tools relevant when Python is detected."""
    return [
        _tool("ruff", is_required=False, install_hint="uv tool install ruff"),
    ]


def _shell_tools() -> list[ToolStatus]:
    """Optional tools relevant when shell scripts are detected."""
    return [
        _tool("shellcheck", is_required=False, install_hint="brew install shellcheck"),
        _tool("shfmt", is_required=False, install_hint="brew install shfmt"),
    ]


def _yaml_tools() -> list[ToolStatus]:
    """Optional tools relevant when YAML files are detected."""
    return [
        _tool("yamllint", is_required=False, install_hint="brew install yamllint"),
    ]


def _dockerfile_tools() -> list[ToolStatus]:
    """Optional tools relevant when Dockerfiles are detected."""
    return [
        _tool("hadolint", is_required=False, install_hint="brew install hadolint"),
    ]


def _toml_tools() -> list[ToolStatus]:
    """Optional tools relevant when TOML files are detected."""
    return [
        _tool("taplo", is_required=False, install_hint="brew install taplo"),
    ]


def _markdown_tools() -> list[ToolStatus]:
    """Optional tools relevant when Markdown files are detected."""
    return [
        _tool(
            "markdownlint-cli2",
            is_required=False,
            install_hint="bun add -g markdownlint-cli2",
        ),
    ]


def _typescript_tools() -> list[ToolStatus]:
    """Optional tools relevant when TypeScript/JS is detected."""
    return [
        _tool("biome", is_required=False, install_hint="bun add -g @biomejs/biome"),
        _tool("semgrep", is_required=False, install_hint="brew install semgrep"),
    ]


# -- language -> optional-tool-list dispatch table ---------------------------------

_LANGUAGE_TOOL_BUILDERS: dict[str, Callable[[], list[ToolStatus]]] = {
    "python": _python_tools,
    "shell": _shell_tools,
    "yaml": _yaml_tools,
    "dockerfile": _dockerfile_tools,
    "toml": _toml_tools,
    "markdown": _markdown_tools,
    "typescript": _typescript_tools,
}


# -- stdout table ------------------------------------------------------------------


def _print_table_header() -> None:
    """Print the header row of the system-check table."""
    print(f"{'tool':<{_COL_TOOL}}{'kind':<{_COL_KIND}}{'status':<{_COL_STATUS}}{'install hint'}")
    print("-" * (_COL_TOOL + _COL_KIND + _COL_STATUS + 30))


def _print_tool_row(tool: ToolStatus) -> None:
    """Print a single row in the system-check table.

    Args:
        tool: ToolStatus to render.
    """
    kind_label = "required" if tool.is_required else "optional"
    status_label = "found" if tool.is_available else "MISSING"
    hint_label = "" if tool.is_available else tool.install_hint
    print(
        f"{tool.name:<{_COL_TOOL}}"
        f"{kind_label:<{_COL_KIND}}"
        f"{status_label:<{_COL_STATUS}}"
        f"{hint_label}"
    )


# -- public API --------------------------------------------------------------------


def check_system_tools(detection: DetectionResult) -> list[ToolStatus]:
    """Verify that required and optional CLI tools are available.

    Prints a human-readable table to stdout. Calls sys.exit(1) when any
    required tool is missing -- there is no fallback.

    Args:
        detection: Language detection results from the scan phase.

    Returns:
        Complete list of ToolStatus entries for every checked tool.
    """
    collected_tools: list[ToolStatus] = []

    # -- always-required tools -------------------------------------------------
    collected_tools.append(
        _tool("jaq", is_required=True, install_hint="brew install jaq"),
    )

    # -- language-conditional required tools ------------------------------------
    if detection.is_enabled("python"):
        uv_hint = "curl -LsSf https://astral.sh/uv/install.sh | sh"
        collected_tools.append(
            _tool("uv", is_required=True, install_hint=uv_hint),
        )

    if detection.is_enabled("typescript"):
        collected_tools.append(
            _tool("bun", is_required=True, install_hint="curl -fsSL https://bun.sh/install | bash"),
        )

    # -- optional per-language tools -------------------------------------------
    for language_name, builder_fn in _LANGUAGE_TOOL_BUILDERS.items():
        if detection.is_enabled(language_name):
            collected_tools.extend(builder_fn())

    # also add shellcheck/shfmt for python projects (scripts often live alongside)
    if detection.is_enabled("python") and not detection.is_enabled("shell"):
        collected_tools.extend(_shell_tools())

    # -- print the table -------------------------------------------------------
    _print_table_header()
    for tool_entry in collected_tools:
        _print_tool_row(tool_entry)

    # -- crash on missing required tools ---------------------------------------
    missing_required = [t for t in collected_tools if t.is_required and not t.is_available]
    if missing_required:
        missing_names = ", ".join(t.name for t in missing_required)
        print(f"\nFATAL: required tools missing: {missing_names}")
        for missing_tool in missing_required:
            print(f"  -> {missing_tool.name}: {missing_tool.install_hint}")
        sys.exit(1)

    return collected_tools
