"""Typer CLI for plankton: init, status, and uninstall commands.

Entry point is the ``plankton`` command registered in pyproject.toml.
All subcommands accept a --target flag to specify the project directory
(defaults to the current working directory).
"""

import sys
from pathlib import Path
from typing import Annotated

import typer

from plankton_hooks.install import run_init, run_status, run_uninstall

app = typer.Typer(
    name="plankton",
    help="write-time code quality enforcement for Claude Code",
    no_args_is_help=True,
)

# typer requires Option() in defaults, which trips B008/FBT/PTH201.
# using Annotated[] avoids all of those.

TargetArg = Annotated[
    Path,
    typer.Option("--target", "-t", help="target project directory (default: cwd)"),
]


def _resolve_target(target: Path) -> Path:
    """Resolve and validate the target directory.

    Args:
        target: Path provided by the user (may be relative).

    Returns:
        Resolved absolute path.
    """
    resolved = target.resolve()
    if not resolved.is_dir():
        print(f"FATAL: target directory does not exist: {resolved}")
        sys.exit(1)
    return resolved


@app.command()
def init(
    target: TargetArg = Path(),
    *,
    python: Annotated[
        bool,
        typer.Option("--python", help="force python detection on"),
    ] = False,
    typescript: Annotated[
        bool,
        typer.Option("--typescript", help="force typescript detection on"),
    ] = False,
    all_languages: Annotated[
        bool,
        typer.Option("--all-languages", help="force all languages on"),
    ] = False,
    skip_deps: Annotated[
        bool,
        typer.Option("--skip-deps", help="skip dev dep installation"),
    ] = False,
) -> None:
    """Install plankton into a project directory.

    Detects languages, copies hook scripts, generates config, installs linter
    configs, adds dev dependencies, and updates CLAUDE.md.
    """
    resolved = _resolve_target(target)
    run_init(
        resolved,
        force_python=python,
        force_typescript=typescript,
        force_all=all_languages,
        skip_deps=skip_deps,
    )


@app.command()
def status(target: TargetArg = Path()) -> None:
    """Show plankton installation status for a project directory."""
    resolved = _resolve_target(target)
    run_status(resolved)


@app.command()
def uninstall(target: TargetArg = Path()) -> None:
    """Remove plankton from a project directory.

    Removes hook scripts, settings.json entries, and the CLAUDE.md section.
    Linter configs and dev dependencies are left in place.
    """
    resolved = _resolve_target(target)
    run_uninstall(resolved)
