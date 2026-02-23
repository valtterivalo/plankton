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


_JS_ADD_COMMANDS: dict[str, list[str]] = {
    "pnpm": ["pnpm", "add", "--save-dev"],
    "yarn": ["yarn", "add", "--dev"],
    "bun": ["bun", "add", "--dev"],
    "npm": ["npm", "install", "--save-dev"],
}


def install_ts_deps(target: Path, *, js_package_manager: str = "npm") -> None:
    """Install TypeScript dev dependencies into the target project.

    Uses the detected JS package manager (pnpm, yarn, bun, or npm).
    No error handling -- a non-zero exit code will raise
    subprocess.CalledProcessError and crash the installer.

    Args:
        target: Root directory of the TypeScript project (must contain
                package.json).
        js_package_manager: Which package manager to use. Detected
            from lockfiles by the caller.
    """
    base_cmd = _JS_ADD_COMMANDS.get(js_package_manager)
    if base_cmd is None:
        msg = f"unknown js package manager: {js_package_manager}"
        raise ValueError(msg)

    dep_list = " ".join(TS_DEV_DEPS)
    print(f"installing typescript dev deps via {js_package_manager}: {dep_list}")
    subprocess.run(  # noqa: S603
        [*base_cmd, *TS_DEV_DEPS],
        cwd=target,
        check=True,
    )
