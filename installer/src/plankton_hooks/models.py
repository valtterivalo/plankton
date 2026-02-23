"""Typed data models for the plankton installer.

Enums and frozen dataclasses that represent detection results, file actions,
and tool availability throughout the installation pipeline.
"""

from dataclasses import dataclass
from enum import Enum


class LanguageDetection(Enum):
    """Whether a language was detected, not found, or forced by the user."""

    DETECTED = "detected"
    NOT_DETECTED = "not_detected"
    FORCED = "forced"


class AppendAction(Enum):
    """Outcome of writing to a config or settings file.

    CREATED means the file did not exist and was written from scratch.
    UPDATED means an existing file was modified in place.
    APPENDED means content was added to the end of an existing file.
    """

    CREATED = "created"
    UPDATED = "updated"
    APPENDED = "appended"


class CopyAction(Enum):
    """Outcome of copying a linter config file into the target project.

    INSTALLED means the file was written to the target.
    SKIPPED means the file already existed and was left alone.
    NOT_APPLICABLE means the language is not relevant to the target project.
    """

    INSTALLED = "installed"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class ToolStatus:
    """Availability of a single external CLI tool (ruff, shellcheck, etc.).

    Attributes:
        name: Executable name as it appears on PATH.
        is_required: Whether the installation should fail without this tool.
        is_available: Whether the tool was found on PATH.
        install_hint: Human-readable install instruction shown when missing.
    """

    name: str
    is_required: bool
    is_available: bool
    install_hint: str


@dataclass(frozen=True)
class DetectionResult:
    """Aggregated language detection results for every supported language.

    Each field holds a LanguageDetection enum value indicating whether that
    language was found in the target project, not found, or forced on by
    the user.

    Attributes:
        python: Detection state for Python.
        typescript: Detection state for TypeScript / JavaScript.
        shell: Detection state for shell scripts.
        yaml: Detection state for YAML files.
        json: Detection state for JSON files.
        toml: Detection state for TOML files.
        dockerfile: Detection state for Dockerfiles.
        markdown: Detection state for Markdown files.
        js_package_manager: Detected JS package manager ("pnpm", "yarn",
            "bun", or "npm"). None when typescript is not enabled.
    """

    python: LanguageDetection
    typescript: LanguageDetection
    shell: LanguageDetection
    yaml: LanguageDetection
    json: LanguageDetection
    toml: LanguageDetection
    dockerfile: LanguageDetection
    markdown: LanguageDetection
    js_package_manager: str | None = None

    def is_enabled(self, lang: str) -> bool:
        """Return True if the given language is DETECTED or FORCED.

        Args:
            lang: Lowercase language name matching one of the dataclass fields
                  (e.g. "python", "typescript", "shell").

        Returns:
            True when the language status is DETECTED or FORCED.

        Raises:
            AttributeError: If lang does not match any field on this dataclass.
        """
        status: LanguageDetection = getattr(self, lang)
        return status in {LanguageDetection.DETECTED, LanguageDetection.FORCED}


@dataclass(frozen=True)
class ConfigCopyResult:
    """Outcome of copying a single linter config file.

    Attributes:
        filename: Name of the config file (e.g. ".ruff.toml").
        action: What happened when the installer tried to place the file.
    """

    filename: str
    action: CopyAction
