"""Sentinel-based idempotent CLAUDE.md management.

Manages the plankton-owned section inside a project's CLAUDE.md file using
HTML comment sentinels. The section content is read from an embedded template
shipped with the package. Supports append, update, and removal operations,
all idempotent.
"""

from importlib import resources
from pathlib import Path

from plankton_hooks.models import AppendAction

# -- sentinel markers used to delimit the plankton-owned section ---------------

SENTINEL_START = "<!-- plankton:start -->"
SENTINEL_END = "<!-- plankton:end -->"


def _load_template() -> str:
    """Load the CLAUDE.md section template from the embedded package data.

    Uses importlib.resources to read the template so it works both from source
    and from an installed wheel.

    Returns:
        The raw template string with sentinels NOT included (they are added
        by the caller).
    """
    template_ref = resources.files("plankton_hooks._embedded.templates").joinpath(
        "claude_md_section.md",
    )
    return template_ref.read_text(encoding="utf-8")


def _build_section() -> str:
    """Build the full sentinel-wrapped section ready for insertion.

    Returns:
        String containing SENTINEL_START, the template content, and SENTINEL_END.
    """
    template_content = _load_template()
    return f"{SENTINEL_START}\n{template_content}\n{SENTINEL_END}"


def append_claude_md(target: Path) -> AppendAction:
    """Idempotently add or update the plankton section in CLAUDE.md.

    Three cases are handled:
    1. File does not exist: create it with just the sentinel-wrapped section.
       Returns CREATED.
    2. SENTINEL_START already present: replace everything between start and end
       sentinels (inclusive) with fresh content. Returns UPDATED.
    3. File exists but has no sentinels: append the section to the end with a
       double newline separator. Returns APPENDED.

    Crashes with ValueError if SENTINEL_START is found but SENTINEL_END is not,
    since that indicates a malformed file that should be fixed manually.

    Args:
        target: Root directory of the target project. The CLAUDE.md file is
                expected at target/CLAUDE.md.

    Returns:
        An AppendAction indicating what happened.

    Raises:
        ValueError: If the file contains SENTINEL_START but not SENTINEL_END.
    """
    claude_md_path = target / "CLAUDE.md"
    section = _build_section()

    # -- case 1: file does not exist
    if not claude_md_path.exists():
        claude_md_path.write_text(section + "\n", encoding="utf-8")
        print(f"[claude.md] created {claude_md_path}")
        return AppendAction.CREATED

    existing_content = claude_md_path.read_text(encoding="utf-8")
    has_start_sentinel = SENTINEL_START in existing_content
    has_end_sentinel = SENTINEL_END in existing_content

    # -- malformed state: start without end
    if has_start_sentinel and not has_end_sentinel:
        msg = (
            f"CLAUDE.md contains {SENTINEL_START} but not {SENTINEL_END}. "
            "the file is malformed and must be fixed manually."
        )
        raise ValueError(msg)

    # -- malformed state: end without start
    if not has_start_sentinel and has_end_sentinel:
        msg = (
            f"CLAUDE.md contains {SENTINEL_END} but not {SENTINEL_START}. "
            "the file is malformed and must be fixed manually."
        )
        raise ValueError(msg)

    # -- case 2: sentinels already present, replace the section
    if has_start_sentinel and has_end_sentinel:
        start_idx = existing_content.index(SENTINEL_START)
        end_idx = existing_content.index(SENTINEL_END) + len(SENTINEL_END)

        # -- malformed state: end sentinel appears before start
        if end_idx - len(SENTINEL_END) < start_idx:
            msg = (
                "CLAUDE.md has sentinels in wrong order (end before start). "
                "the file is malformed and must be fixed manually."
            )
            raise ValueError(msg)
        updated_content = existing_content[:start_idx] + section + existing_content[end_idx:]
        claude_md_path.write_text(updated_content, encoding="utf-8")
        print(f"[claude.md] updated existing section in {claude_md_path}")
        return AppendAction.UPDATED

    # -- case 3: file exists but no sentinels, append to end
    separator = "\n\n" if existing_content and not existing_content.endswith("\n\n") else ""
    if (
        existing_content
        and existing_content.endswith("\n")
        and not existing_content.endswith("\n\n")
    ):
        separator = "\n"
    elif existing_content and not existing_content.endswith("\n"):
        separator = "\n\n"
    else:
        separator = ""

    appended_content = existing_content + separator + section + "\n"
    claude_md_path.write_text(appended_content, encoding="utf-8")
    print(f"[claude.md] appended plankton section to {claude_md_path}")
    return AppendAction.APPENDED


def remove_claude_md_section(target: Path) -> bool:
    """Remove the plankton-owned section from CLAUDE.md.

    Finds the sentinel-delimited block and removes it, including the sentinels
    themselves. Cleans up any excess blank lines left behind.

    Args:
        target: Root directory of the target project.

    Returns:
        True if the sentinel section was found and removed, False if no
        sentinels were present (or the file does not exist).
    """
    claude_md_path = target / "CLAUDE.md"

    if not claude_md_path.exists():
        print("[claude.md] no CLAUDE.md found, nothing to remove")
        return False

    existing_content = claude_md_path.read_text(encoding="utf-8")

    if SENTINEL_START not in existing_content:
        print("[claude.md] no plankton section found, nothing to remove")
        return False

    if SENTINEL_END not in existing_content:
        msg = (
            f"CLAUDE.md contains {SENTINEL_START} but not {SENTINEL_END}. "
            "the file is malformed and must be fixed manually."
        )
        raise ValueError(msg)

    start_idx = existing_content.index(SENTINEL_START)
    end_idx = existing_content.index(SENTINEL_END) + len(SENTINEL_END)

    if end_idx - len(SENTINEL_END) < start_idx:
        msg = (
            "CLAUDE.md has sentinels in wrong order (end before start). "
            "the file is malformed and must be fixed manually."
        )
        raise ValueError(msg)

    # remove the section and clean up surrounding whitespace
    before = existing_content[:start_idx].rstrip("\n")
    after = existing_content[end_idx:].lstrip("\n")

    if before and after:
        cleaned_content = before + "\n\n" + after
    elif before:
        cleaned_content = before + "\n"
    elif after:
        cleaned_content = after
    else:
        cleaned_content = ""

    claude_md_path.write_text(cleaned_content, encoding="utf-8")
    print(f"[claude.md] removed plankton section from {claude_md_path}")
    return True
