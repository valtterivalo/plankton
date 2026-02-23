"""Dev dependency installation for Python and TypeScript targets.

Runs uv or bun to add linting/formatting dev dependencies into the
target project. Subprocess failures propagate uncaught -- if the
package manager crashes, so does the installer.
"""

import subprocess
from pathlib import Path

# -- dependency lists ----------------------------------------------------------

PYTHON_DEV_DEPS: list[str] = [
    "ruff",
    "ty",
    "vulture",
    "bandit",
    "flake8",
    "flake8-pydantic",
    "flake8-async",
    "yamllint",
]

TS_DEV_DEPS: list[str] = [
    "@biomejs/biome",
]


# -- installers ----------------------------------------------------------------


def install_python_deps(target: Path) -> None:
    """Install Python dev dependencies via uv into the target project.

    Runs ``uv add --dev <packages>`` inside *target*. No error handling --
    a non-zero exit code from uv will raise subprocess.CalledProcessError
    and crash the installer, which is the intended behaviour.

    Args:
        target: Root directory of the Python project (must contain
                pyproject.toml or be initialisable by uv).
    """
    dep_list = " ".join(PYTHON_DEV_DEPS)
    print(f"installing python dev deps via uv: {dep_list}")
    subprocess.run(  # noqa: S603
        ["uv", "add", "--dev", *PYTHON_DEV_DEPS],  # noqa: S607
        cwd=target,
        check=True,
    )


def install_ts_deps(target: Path) -> None:
    """Install TypeScript dev dependencies via bun into the target project.

    Runs ``bun add --dev <packages>`` inside *target*. No error handling --
    a non-zero exit code from bun will raise subprocess.CalledProcessError
    and crash the installer, which is the intended behaviour.

    Args:
        target: Root directory of the TypeScript project (must contain
                package.json or be initialisable by bun).
    """
    dep_list = " ".join(TS_DEV_DEPS)
    print(f"installing typescript dev deps via bun: {dep_list}")
    subprocess.run(  # noqa: S603
        ["bun", "add", "--dev", *TS_DEV_DEPS],  # noqa: S607
        cwd=target,
        check=True,
    )
