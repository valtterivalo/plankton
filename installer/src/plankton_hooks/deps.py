"""Dev dependency installation for Python, TypeScript, and system-level targets.

Runs uv or bun to add linting/formatting dev dependencies into the
target project. For C/C++ tools, installs via brew on macOS.
Subprocess failures propagate uncaught -- if the package manager
crashes, so does the installer.
"""

import platform
import shutil
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

    Runs ``uv add --dev <packages>`` inside *target*. Skips if no
    pyproject.toml exists at root (Python may have been detected from .py
    files in subdirectories). A non-zero exit code from uv will raise
    subprocess.CalledProcessError and crash the installer.

    Args:
        target: Root directory of the Python project.
    """
    if not (target / "pyproject.toml").exists():
        print("[skip] no pyproject.toml at project root, skipping python deps")
        return

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

    Uses the detected JS package manager (pnpm, yarn, bun, or npm). Skips
    if no package.json exists at root (TypeScript may have been detected
    from .ts files in subdirectories). A non-zero exit code will raise
    subprocess.CalledProcessError and crash the installer.

    Args:
        target: Root directory of the TypeScript project.
        js_package_manager: Which package manager to use. Detected
            from lockfiles by the caller.
    """
    if not (target / "package.json").exists():
        print("[skip] no package.json at project root, skipping typescript deps")
        return

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


# -- brew paths for keg-only formulae -----------------------------------------

_BREW_LLVM_BIN = Path("/opt/homebrew/opt/llvm/bin")
_BREW_LLVM_BIN_X86 = Path("/usr/local/opt/llvm/bin")

C_CPP_BREW_PACKAGES: list[str] = ["llvm", "cppcheck"]


def _find_brew_llvm_bin() -> Path | None:
    """Find the brew llvm bin directory if it exists."""
    if _BREW_LLVM_BIN.is_dir():
        return _BREW_LLVM_BIN
    if _BREW_LLVM_BIN_X86.is_dir():
        return _BREW_LLVM_BIN_X86
    return None


def install_c_cpp_deps() -> None:
    """Install C/C++ system tools via brew on macOS.

    Installs llvm (for clang-format, clang-tidy) and cppcheck via
    homebrew. On non-macOS platforms, prints instructions and skips.

    Since brew's llvm is keg-only (not linked to /usr/local/bin),
    after installation we symlink clang-format, clang-tidy into
    a brew-visible path.
    """
    if platform.system() != "Darwin":
        print("  [skip] C/C++ tools require manual install on non-macOS")
        print("  install: clang-format, clang-tidy (from LLVM), cppcheck")
        return

    if shutil.which("brew") is None:
        print("  [skip] homebrew not found, install C/C++ tools manually")
        return

    # install missing packages
    for pkg in C_CPP_BREW_PACKAGES:
        # check if already installed (brew list exits 0 if installed)
        result = subprocess.run(  # noqa: S603
            ["brew", "list", pkg],  # noqa: S607
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            print(f"  [ok] {pkg} already installed")
        else:
            print(f"  installing {pkg} via brew...")
            subprocess.run(  # noqa: S603
                ["brew", "install", pkg],  # noqa: S607
                check=True,
            )

    # symlink llvm tools to /opt/homebrew/bin (or /usr/local/bin) so they're on PATH
    llvm_bin = _find_brew_llvm_bin()
    if llvm_bin is None:
        print("  [warn] llvm installed but bin dir not found")
        return

    brew_prefix = subprocess.run(  # noqa: S603
        ["brew", "--prefix"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    link_dir = Path(brew_prefix) / "bin"

    for tool in ("clang-format", "clang-tidy"):
        source = llvm_bin / tool
        target_link = link_dir / tool
        if target_link.exists() or target_link.is_symlink():
            print(f"  [ok] {tool} already on PATH")
        elif source.exists():
            target_link.symlink_to(source)
            print(f"  [linked] {tool} -> {source}")
        else:
            print(f"  [warn] {source} not found")
