"""Core installation orchestration for plankton.

Coordinates the full init/uninstall workflow: detection, tool checks, hook script
copying, config generation, settings merge, linter config installation, dev deps,
and CLAUDE.md management. Each step prints its own status output to stdout.
"""

import shutil
import stat
from importlib import resources
from pathlib import Path

from plankton_hooks.claude_md import SENTINEL_START, append_claude_md, remove_claude_md_section
from plankton_hooks.config_gen import generate_config, write_config
from plankton_hooks.deps import install_python_deps, install_ts_deps
from plankton_hooks.detect import detect_languages
from plankton_hooks.models import ConfigCopyResult, CopyAction, DetectionResult
from plankton_hooks.settings_merge import merge_settings, remove_plankton_hooks
from plankton_hooks.system_check import check_system_tools

# -- embedded hook scripts to install -----------------------------------------

_HOOK_SCRIPTS: list[str] = [
    "multi_linter.sh",
    "protect_linter_configs.sh",
    "enforce_package_managers.sh",
    "stop_config_guardian.sh",
    "approve_configs.sh",
]

# -- linter config mapping: language -> list of (source path in _embedded, target filename)

_LINTER_CONFIGS: dict[str, list[tuple[str, str]]] = {
    "python": [
        ("configs/python/.ruff.toml", ".ruff.toml"),
        ("configs/python/ty.toml", "ty.toml"),
        ("configs/python/.flake8", ".flake8"),
    ],
    "shell": [
        ("configs/shell/.shellcheckrc", ".shellcheckrc"),
    ],
    "yaml": [
        ("configs/yaml/.yamllint", ".yamllint"),
    ],
    "dockerfile": [
        ("configs/dockerfile/.hadolint.yaml", ".hadolint.yaml"),
    ],
    "toml": [
        ("configs/toml/taplo.toml", "taplo.toml"),
    ],
    "markdown": [
        ("configs/markdown/.markdownlint.jsonc", ".markdownlint.jsonc"),
        ("configs/markdown/.markdownlint-cli2.jsonc", ".markdownlint-cli2.jsonc"),
    ],
    "typescript": [
        ("configs/ts/biome.json", "biome.json"),
    ],
    "general": [
        ("configs/general/.jscpd.json", ".jscpd.json"),
    ],
}


def _embedded_root() -> Path:
    """Resolve the root of the _embedded package data directory.

    Returns:
        Path to the _embedded directory.

    Raises:
        RuntimeError: If the package was installed as a zip (not unpacked).
            hatchling builds unpacked wheels by default, so this should not
            happen under normal circumstances.
    """
    ref = resources.files("plankton_hooks._embedded")
    root = Path(str(ref))
    if not root.is_dir():
        msg = (
            "plankton embedded data not found on disk. "
            "this usually means the package was installed from a zip wheel. "
            "reinstall with: uvx --reinstall plankton-hooks"
        )
        raise RuntimeError(msg)
    return root


def _copy_hook_scripts(target: Path) -> None:
    """Copy all plankton hook scripts into target/.claude/hooks/.

    Always overwrites existing scripts -- these are plankton-managed, not
    user-edited. Sets the executable bit on each script.

    Args:
        target: Root directory of the target project.
    """
    hooks_dir = target / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    embedded = _embedded_root()
    for script_name in _HOOK_SCRIPTS:
        source = embedded / "hooks" / script_name
        dest = hooks_dir / script_name
        shutil.copy2(source, dest)
        # set executable: owner rwx, group rx, other rx
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"[hooks] installed {script_name}")


def _remove_hook_scripts(target: Path) -> None:
    """Remove plankton hook scripts and config.json from target/.claude/hooks/.

    Removes scripts that plankton manages plus the generated config.json.
    Leaves other files untouched.

    Args:
        target: Root directory of the target project.
    """
    hooks_dir = target / ".claude" / "hooks"
    if not hooks_dir.exists():
        print("[hooks] no hooks directory found")
        return

    for script_name in _HOOK_SCRIPTS:
        script_path = hooks_dir / script_name
        if script_path.exists():
            script_path.unlink()
            print(f"[hooks] removed {script_name}")

    # also remove config.json
    config_path = hooks_dir / "config.json"
    if config_path.exists():
        config_path.unlink()
        print("[hooks] removed config.json")


def _copy_linter_configs(target: Path, detection: DetectionResult) -> list[ConfigCopyResult]:
    """Copy linter config files to the project root, skipping existing ones.

    For each detected language, copies the corresponding config files from
    embedded package data. If a file already exists in the target, it is
    skipped with a message. The "general" category (.jscpd.json) is always
    copied regardless of detection.

    Args:
        target: Root directory of the target project.
        detection: Language detection results from the scan phase.

    Returns:
        List of ConfigCopyResult entries showing what happened to each file.
    """
    results: list[ConfigCopyResult] = []
    embedded = _embedded_root()

    # determine which language groups to process
    all_langs = ("python", "shell", "yaml", "dockerfile", "toml", "markdown", "typescript")
    language_groups_to_copy: list[str] = [
        "general",
        *[lang for lang in all_langs if detection.is_enabled(lang)],
    ]

    for group in language_groups_to_copy:
        configs = _LINTER_CONFIGS.get(group, [])
        for embedded_path, target_filename in configs:
            dest = target / target_filename
            if dest.exists():
                print(f"[skip] {target_filename} already exists")
                results.append(
                    ConfigCopyResult(filename=target_filename, action=CopyAction.SKIPPED),
                )
            else:
                source = embedded / embedded_path
                shutil.copy2(source, dest)
                print(f"[installed] {target_filename}")
                results.append(
                    ConfigCopyResult(filename=target_filename, action=CopyAction.INSTALLED),
                )

    return results


# -- public API ---------------------------------------------------------------


def run_init(
    target: Path,
    *,
    force_python: bool = False,
    force_typescript: bool = False,
    force_all: bool = False,
    skip_deps: bool = False,
) -> None:
    """Run the full plankton installation flow.

    Steps:
    1. Detect languages
    2. Check system tools (crash if jaq missing)
    3. Copy hook scripts
    4. Generate and write config.json
    5. Merge settings.json
    6. Copy linter configs (skip existing)
    7. Install dev dependencies (unless --skip-deps)
    8. Append to CLAUDE.md

    Args:
        target: Root directory of the target project. Must exist.
        force_python: Force Python detection on.
        force_typescript: Force TypeScript detection on.
        force_all: Force all languages on.
        skip_deps: Skip dev dependency installation.
    """
    print(f"plankton init -> {target}\n")

    # step 1: detect
    print("--- detecting languages ---")
    detection = detect_languages(
        target,
        force_python=force_python,
        force_typescript=force_typescript,
        force_all=force_all,
    )

    # step 2: system tools
    print("\n--- checking system tools ---")
    check_system_tools(detection)

    # step 3: hook scripts
    print("\n--- installing hook scripts ---")
    _copy_hook_scripts(target)

    # step 4: config.json
    print("\n--- generating config.json ---")
    config = generate_config(detection)
    write_config(target, config)

    # step 5: settings.json
    print("\n--- merging settings.json ---")
    merge_settings(target)

    # step 6: linter configs
    print("\n--- installing linter configs ---")
    copy_results = _copy_linter_configs(target, detection)

    # step 7: dev deps
    if not skip_deps:
        print("\n--- installing dev dependencies ---")
        if detection.is_enabled("python"):
            install_python_deps(target)
        if detection.is_enabled("typescript"):
            install_ts_deps(target)
    else:
        print("\n--- skipping dev dependencies (--skip-deps) ---")

    # step 8: CLAUDE.md
    print("\n--- updating CLAUDE.md ---")
    append_claude_md(target)

    # summary
    installed_count = sum(1 for r in copy_results if r.action == CopyAction.INSTALLED)
    skipped_count = sum(1 for r in copy_results if r.action == CopyAction.SKIPPED)
    print(f"\ndone. {installed_count} configs installed, {skipped_count} skipped (already exist).")


def run_update(
    target: Path,
    *,
    force_python: bool = False,
    force_typescript: bool = False,
    force_all: bool = False,
) -> None:
    """Refresh plankton hooks and config without touching linter configs or deps.

    Useful after upstream plankton changes. Overwrites hook scripts and
    regenerates config.json, but leaves linter configs, CLAUDE.md, and
    dev dependencies untouched (user may have customized them).

    Args:
        target: Root directory of the target project. Must exist.
        force_python: Force Python detection on.
        force_typescript: Force TypeScript detection on.
        force_all: Force all languages on.
    """
    print(f"plankton update -> {target}\n")

    # detect languages (needed for config.json regeneration)
    print("--- detecting languages ---")
    detection = detect_languages(
        target,
        force_python=force_python,
        force_typescript=force_typescript,
        force_all=force_all,
    )

    # system tools check
    print("\n--- checking system tools ---")
    check_system_tools(detection)

    # overwrite hook scripts
    print("\n--- updating hook scripts ---")
    _copy_hook_scripts(target)

    # regenerate config.json
    print("\n--- regenerating config.json ---")
    config = generate_config(detection)
    write_config(target, config)

    # re-merge settings.json (idempotent)
    print("\n--- merging settings.json ---")
    merge_settings(target)

    print("\ndone. linter configs, CLAUDE.md, and dev deps were left in place.")


def run_uninstall(target: Path) -> None:
    """Remove plankton from a target project.

    Removes hook scripts, config.json, plankton entries from settings.json,
    and the plankton section from CLAUDE.md. Does NOT remove linter configs
    or dev dependencies (user may have customized them).

    Args:
        target: Root directory of the target project.
    """
    print(f"plankton uninstall -> {target}\n")

    print("--- removing hook scripts ---")
    _remove_hook_scripts(target)

    print("\n--- cleaning settings.json ---")
    remove_plankton_hooks(target)

    print("\n--- cleaning CLAUDE.md ---")
    remove_claude_md_section(target)

    print("\ndone. linter configs and dev deps were left in place.")


def run_status(target: Path) -> None:
    """Print installation status for a target project.

    Read-only inspection: checks which hooks are installed, which configs
    exist, and which system tools are available.

    Args:
        target: Root directory of the target project.
    """
    print(f"plankton status -> {target}\n")

    # hook scripts
    hooks_dir = target / ".claude" / "hooks"
    print("--- hook scripts ---")
    for script_name in _HOOK_SCRIPTS:
        script_path = hooks_dir / script_name
        is_present = script_path.exists()
        status_label = "installed" if is_present else "missing"
        print(f"  {script_name}: {status_label}")

    # config.json
    config_path = hooks_dir / "config.json"
    is_config_present = config_path.exists()
    print(f"  config.json: {'present' if is_config_present else 'missing'}")

    # settings.json
    settings_path = target / ".claude" / "settings.json"
    print("\n--- settings.json ---")
    if settings_path.exists():
        print(f"  found at {settings_path}")
    else:
        print("  not found")

    # linter configs
    print("\n--- linter configs ---")
    all_config_files = set()
    for configs in _LINTER_CONFIGS.values():
        for _, filename in configs:
            all_config_files.add(filename)
    for filename in sorted(all_config_files):
        is_present = (target / filename).exists()
        status_label = "present" if is_present else "not installed"
        print(f"  {filename}: {status_label}")

    # CLAUDE.md
    print("\n--- CLAUDE.md ---")
    claude_md_path = target / "CLAUDE.md"
    if claude_md_path.exists():
        content = claude_md_path.read_text(encoding="utf-8")
        has_plankton_section = SENTINEL_START in content
        print(f"  plankton section: {'present' if has_plankton_section else 'not found'}")
    else:
        print("  CLAUDE.md not found")

    # system tools — quick check without crashing on missing required tools
    print("\n--- system tools ---")
    tools_to_check = [
        "jaq",
        "ruff",
        "uv",
        "bun",
        "shellcheck",
        "shfmt",
        "yamllint",
        "hadolint",
        "taplo",
        "markdownlint-cli2",
        "biome",
        "semgrep",
    ]
    for tool_name in tools_to_check:
        is_available = shutil.which(tool_name) is not None
        status_label = "found" if is_available else "not found"
        print(f"  {tool_name}: {status_label}")


def run_dry_run(
    target: Path,
    *,
    force_python: bool = False,
    force_typescript: bool = False,
    force_all: bool = False,
) -> None:
    """Preview what plankton init would do without making changes.

    Runs detection and reports what hooks, configs, and deps would be
    installed. Does not modify any files.

    Args:
        target: Root directory of the target project. Must exist.
        force_python: Force Python detection on.
        force_typescript: Force TypeScript detection on.
        force_all: Force all languages on.
    """
    from plankton_hooks.deps import PYTHON_DEV_DEPS, TS_DEV_DEPS

    print(f"plankton init --dry-run -> {target}\n")

    # detect languages
    print("--- language detection ---")
    detection = detect_languages(
        target,
        force_python=force_python,
        force_typescript=force_typescript,
        force_all=force_all,
    )

    # hook scripts
    print("\n--- hook scripts (always overwritten) ---")
    for script_name in _HOOK_SCRIPTS:
        print(f"  would install: {script_name}")

    # linter configs
    print("\n--- linter configs ---")
    all_langs = ("python", "shell", "yaml", "dockerfile", "toml", "markdown", "typescript")
    language_groups = [
        "general",
        *[lang for lang in all_langs if detection.is_enabled(lang)],
    ]
    would_install = 0
    would_skip = 0
    for group in language_groups:
        configs = _LINTER_CONFIGS.get(group, [])
        for _embedded_path, target_filename in configs:
            dest = target / target_filename
            if dest.exists():
                print(f"  [skip] {target_filename} (already exists)")
                would_skip += 1
            else:
                print(f"  [would install] {target_filename}")
                would_install += 1

    # dev deps
    print("\n--- dev dependencies ---")
    if detection.is_enabled("python"):
        print(f"  python: {', '.join(PYTHON_DEV_DEPS)}")
    if detection.is_enabled("typescript"):
        print(f"  typescript: {', '.join(TS_DEV_DEPS)}")
    if not detection.is_enabled("python") and not detection.is_enabled("typescript"):
        print("  none (no python or typescript detected)")

    # CLAUDE.md
    print("\n--- CLAUDE.md ---")
    claude_md_path = target / "CLAUDE.md"
    if claude_md_path.exists():
        content = claude_md_path.read_text(encoding="utf-8")
        if SENTINEL_START in content:
            print("  would update existing plankton section")
        else:
            print("  would append plankton section")
    else:
        print("  would create CLAUDE.md with plankton section")

    print(f"\nsummary: {would_install} configs to install, {would_skip} to skip.")
