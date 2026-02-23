"""Language detection for target projects.

Performs a shallow scan (root directory + one level of subdirectories) to
determine which languages and file formats are present in a project. Used by
the installer to decide which linter configs to copy and which hooks to enable.
"""

from pathlib import Path

from plankton_hooks.models import DetectionResult, LanguageDetection

# -- extension / filename mappings used during detection ---------------------

PYTHON_MARKERS: set[str] = {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"}
TYPESCRIPT_MARKERS: set[str] = {"package.json", "tsconfig.json"}
PYTHON_EXTENSIONS: set[str] = {".py"}
TYPESCRIPT_EXTENSIONS: set[str] = {".ts", ".tsx", ".js", ".jsx"}
SHELL_EXTENSIONS: set[str] = {".sh"}
YAML_EXTENSIONS: set[str] = {".yml", ".yaml"}
TOML_EXTENSIONS: set[str] = {".toml"}
MARKDOWN_EXTENSIONS: set[str] = {".md"}


_SKIP_DIRS: set[str] = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".claude",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


def _collect_shallow_files(target: Path) -> list[Path]:
    """Collect files from root and one level of subdirectories.

    This intentionally avoids rglob to keep scanning fast and predictable.
    Only iterates into immediate child directories (e.g. src/), not deeper.
    Skips known dependency/cache directories (node_modules, .venv, etc.).

    Args:
        target: Root directory of the project to scan.

    Returns:
        Flat list of Path objects for every file found at depth 0 or 1.
    """
    found_files: list[Path] = []
    for entry in target.iterdir():
        if entry.is_file():
            found_files.append(entry)
        elif entry.is_dir() and entry.name not in _SKIP_DIRS and not entry.name.startswith("."):
            found_files.extend(child for child in entry.iterdir() if child.is_file())
    return found_files


def _has_extension(files: list[Path], extensions: set[str]) -> Path | None:
    """Return the first file matching any of the given extensions, or None.

    Args:
        files: Pre-collected list of paths to check.
        extensions: Set of suffixes including the dot (e.g. {".py"}).

    Returns:
        The first matching Path, or None if no file matches.
    """
    for file in files:
        if file.suffix in extensions:
            return file
    return None


def _has_marker(files: list[Path], markers: set[str]) -> Path | None:
    """Return the first file whose name matches a known marker, or None.

    Args:
        files: Pre-collected list of paths to check.
        markers: Set of exact filenames (e.g. {"pyproject.toml"}).

    Returns:
        The first matching Path, or None if no file matches.
    """
    for file in files:
        if file.name in markers:
            return file
    return None


def _is_dockerfile(path: Path) -> bool:
    """Check whether a path looks like a Dockerfile.

    Matches: Dockerfile, Dockerfile.*, *.dockerfile (case-insensitive on suffix).

    Args:
        path: File path to inspect.

    Returns:
        True if the filename matches a Dockerfile naming convention.
    """
    name = path.name
    if name == "Dockerfile" or name.startswith("Dockerfile."):
        return True
    return name.lower().endswith(".dockerfile")


def _detect_single(
    label: str,
    files: list[Path],
    *,
    markers: set[str] | None = None,
    extensions: set[str] | None = None,
) -> tuple[LanguageDetection, str]:
    """Run detection for a single language and print the result.

    Args:
        label: Human-readable language name for output (e.g. "python").
        files: Pre-collected shallow file list.
        markers: Exact filenames that signal presence of this language.
        extensions: File suffixes that signal presence of this language.

    Returns:
        Tuple of (detection status, reason string for logging).
    """
    if markers:
        matched_marker = _has_marker(files, markers)
        if matched_marker is not None:
            reason = f"{matched_marker.name} found"
            print(f"[detected] {label} ({reason})")
            return LanguageDetection.DETECTED, reason

    if extensions:
        matched_extension = _has_extension(files, extensions)
        if matched_extension is not None:
            reason = f"*.{matched_extension.suffix.lstrip('.')} file found"
            print(f"[detected] {label} ({reason})")
            return LanguageDetection.DETECTED, reason

    print(f"[not found] {label}")
    return LanguageDetection.NOT_DETECTED, "not found"


def detect_languages(
    target: Path,
    *,
    force_python: bool = False,
    force_typescript: bool = False,
    force_all: bool = False,
) -> DetectionResult:
    """Scan a project directory and determine which languages are present.

    Performs a shallow scan (root + immediate subdirectories) looking for
    known marker files and file extensions. Results can be overridden with
    force flags, which set the language status to FORCED regardless of what
    was found on disk.

    Args:
        target: Root directory of the target project.
        force_python: Force Python detection to FORCED.
        force_typescript: Force TypeScript detection to FORCED.
        force_all: Force every language to FORCED.

    Returns:
        A frozen DetectionResult with the status of each language.
    """
    if force_all:
        print("[forced] all languages enabled by --force-all")
        forced = LanguageDetection.FORCED
        return DetectionResult(
            python=forced,
            typescript=forced,
            shell=forced,
            yaml=forced,
            json=forced,
            toml=forced,
            dockerfile=forced,
            markdown=forced,
        )

    files = _collect_shallow_files(target)

    # -- python --------------------------------------------------------------
    if force_python:
        print("[forced] python")
        python_status = LanguageDetection.FORCED
    else:
        python_status, _ = _detect_single(
            "python",
            files,
            markers=PYTHON_MARKERS,
            extensions=PYTHON_EXTENSIONS,
        )

    # -- typescript / javascript ---------------------------------------------
    if force_typescript:
        print("[forced] typescript")
        typescript_status = LanguageDetection.FORCED
    else:
        typescript_status, _ = _detect_single(
            "typescript",
            files,
            markers=TYPESCRIPT_MARKERS,
            extensions=TYPESCRIPT_EXTENSIONS,
        )

    # -- shell ---------------------------------------------------------------
    shell_status, _ = _detect_single("shell", files, extensions=SHELL_EXTENSIONS)

    # -- yaml ----------------------------------------------------------------
    yaml_status, _ = _detect_single("yaml", files, extensions=YAML_EXTENSIONS)

    # -- json (always detected, it's ubiquitous) -----------------------------
    print("[detected] json (ubiquitous)")
    json_status = LanguageDetection.DETECTED

    # -- toml ----------------------------------------------------------------
    toml_status, _ = _detect_single("toml", files, extensions=TOML_EXTENSIONS)

    # -- dockerfile (custom matching, not extension-based) --------------------
    dockerfile_match = next((f for f in files if _is_dockerfile(f)), None)
    if dockerfile_match is not None:
        print(f"[detected] dockerfile ({dockerfile_match.name} found)")
        dockerfile_status = LanguageDetection.DETECTED
    else:
        print("[not found] dockerfile")
        dockerfile_status = LanguageDetection.NOT_DETECTED

    # -- markdown ------------------------------------------------------------
    markdown_status, _ = _detect_single("markdown", files, extensions=MARKDOWN_EXTENSIONS)

    return DetectionResult(
        python=python_status,
        typescript=typescript_status,
        shell=shell_status,
        yaml=yaml_status,
        json=json_status,
        toml=toml_status,
        dockerfile=dockerfile_status,
        markdown=markdown_status,
    )
