"""
Core implementation for the Code Listing Combiner.

This module contains file discovery, optional directory exclusions, language-aware
statement statistics, timestamp formatting, and safe report replacement.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Pattern, Sequence


# =============================================================================
# Default configuration
# =============================================================================

DEFAULT_EXTENSIONS = {
    # C#
    ".cs",
    ".csx",
    # C / C++
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".cxx",
    ".hpp",
    ".hh",
    ".hxx",
    # Assembly
    ".asm",
    ".s",
    ".inc",
    ".assembler",
    # JVM languages
    ".java",
    ".kt",
    ".kts",
    # JavaScript / TypeScript
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    # Other programming languages
    ".py",
    ".go",
    ".rs",
    ".gd",
    ".gdshader",
    ".lua",
    ".php",
    ".rb",
    ".swift",
    # Scripts, database, and web files
    ".sh",
    ".ps1",
    ".bat",
    ".sql",
    ".html",
    ".css",
    ".scss",
}

DEFAULT_SKIPPED_DIRECTORIES = {
    # Version control and IDE metadata
    ".git",
    ".idea",
    ".vs",
    ".vscode",
    # Engine, language, and test caches
    ".godot",
    ".import",
    ".mono",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "venv",
    "site-packages",
    # Build and package output
    "bin",
    "obj",
    "build",
    "dist",
    "out",
    "target",
    "node_modules",
    "packages",
    "package_cache",
    # Common third-party source directories
    "external",
    "third_party",
    "third-party",
    "vendor",
    "vendors",
    "libs",
    "libraries",
}

DEFAULT_SKIPPED_DIRECTORY_NAMES = frozenset(
    directory.casefold()
    for directory in DEFAULT_SKIPPED_DIRECTORIES
)

IDENTIFIER = r"@?[A-Za-z_][A-Za-z0-9_]*"
ASSEMBLY_IDENTIFIER = r"[A-Za-z_.$?@][A-Za-z0-9_.$?@]*"


# =============================================================================
# Declaration rules
# =============================================================================

@dataclass(frozen=True)
class DeclarationRule:
    """A category label and a regular expression used for approximate counts."""

    label: str
    pattern: Pattern[str]


def make_rule(label: str, pattern: str, flags: int = 0) -> DeclarationRule:
    """Create one multiline declaration-counting rule."""
    return DeclarationRule(
        label=label,
        pattern=re.compile(pattern, re.MULTILINE | flags),
    )


def rule_set(*items: DeclarationRule) -> tuple[DeclarationRule, ...]:
    """Make multi-rule language definitions easier to read."""
    return items


CS_RULES = rule_set(
    make_rule("Records", rf"\brecord(?:\s+(?:class|struct))?\s+{IDENTIFIER}\b"),
    make_rule("Delegates", rf"\bdelegate\s+[^;{{}}()]*?{IDENTIFIER}\s*\("),
    make_rule("Interfaces", rf"\binterface\s+{IDENTIFIER}\b"),
    make_rule("Enums", rf"\benum\s+{IDENTIFIER}\b"),
    make_rule("Structs", rf"\bstruct\s+{IDENTIFIER}\b"),
    make_rule("Classes", rf"\bclass\s+{IDENTIFIER}\b"),
    make_rule("Namespaces", rf"\bnamespace\s+{IDENTIFIER}(?:\s*\.\s*{IDENTIFIER})*"),
)

CPP_RULES = rule_set(
    make_rule("Enums", rf"\benum(?:\s+(?:class|struct))?\s+{IDENTIFIER}\b"),
    make_rule("Classes", rf"\bclass\s+{IDENTIFIER}\b"),
    make_rule("Structs", rf"\bstruct\s+{IDENTIFIER}\b"),
    make_rule("Unions", rf"\bunion\s+{IDENTIFIER}\b"),
    make_rule("Concepts", rf"\bconcept\s+{IDENTIFIER}\b"),
    make_rule("Namespaces", rf"\bnamespace\s+{IDENTIFIER}(?:\s*::\s*{IDENTIFIER})*"),
)

C_RULES = rule_set(
    make_rule("Enums", rf"\benum\s+{IDENTIFIER}\b"),
    make_rule("Structs", rf"\bstruct\s+{IDENTIFIER}\b"),
    make_rule("Unions", rf"\bunion\s+{IDENTIFIER}\b"),
    make_rule("Typedefs", rf"\btypedef\b[^;{{}}]*?\b{IDENTIFIER}\s*;"),
)

ASSEMBLY_RULES = rule_set(
    make_rule("Procedures", rf"^\s*{ASSEMBLY_IDENTIFIER}\s+PROC\b", re.IGNORECASE),
    make_rule(
        "Macros",
        rf"^\s*(?:{ASSEMBLY_IDENTIFIER}\s+MACRO\b|%macro\s+{ASSEMBLY_IDENTIFIER}\b)",
        re.IGNORECASE,
    ),
    make_rule("Labels", rf"^\s*{ASSEMBLY_IDENTIFIER}\s*:"),
)

JAVA_RULES = rule_set(
    make_rule("Annotations", rf"@\s*interface\s+{IDENTIFIER}\b"),
    make_rule("Records", rf"\brecord\s+{IDENTIFIER}\b"),
    make_rule("Interfaces", rf"\binterface\s+{IDENTIFIER}\b"),
    make_rule("Enums", rf"\benum\s+{IDENTIFIER}\b"),
    make_rule("Classes", rf"\bclass\s+{IDENTIFIER}\b"),
    make_rule("Packages", rf"\bpackage\s+{IDENTIFIER}(?:\s*\.\s*{IDENTIFIER})*\s*;"),
)

KOTLIN_RULES = rule_set(
    make_rule("Enums", rf"\benum\s+class\s+{IDENTIFIER}\b"),
    make_rule("Annotations", rf"\bannotation\s+class\s+{IDENTIFIER}\b"),
    make_rule("Objects", rf"\b(?:companion\s+)?object\s+{IDENTIFIER}\b"),
    make_rule("Type aliases", rf"\btypealias\s+{IDENTIFIER}\s*="),
    make_rule("Interfaces", rf"\binterface\s+{IDENTIFIER}\b"),
    make_rule("Classes", rf"\bclass\s+{IDENTIFIER}\b"),
)

TYPESCRIPT_RULES = rule_set(
    make_rule("Enums", rf"\b(?:const\s+)?enum\s+{IDENTIFIER}\b"),
    make_rule("Interfaces", rf"\binterface\s+{IDENTIFIER}\b"),
    make_rule("Type aliases", rf"\btype\s+{IDENTIFIER}(?:<[^>]+>)?\s*="),
    make_rule("Classes", rf"\bclass\s+{IDENTIFIER}\b"),
    make_rule("Namespaces", rf"\b(?:namespace|module)\s+{IDENTIFIER}\b"),
)

PYTHON_RULES = rule_set(
    make_rule("Classes", rf"^\s*class\s+{IDENTIFIER}\b"),
)

GO_RULES = rule_set(
    make_rule("Interfaces", rf"\btype\s+{IDENTIFIER}(?:\[[^\]]+\])?\s+interface\b"),
    make_rule("Structs", rf"\btype\s+{IDENTIFIER}(?:\[[^\]]+\])?\s+struct\b"),
    make_rule("Type aliases", rf"\btype\s+{IDENTIFIER}\s*="),
    make_rule("Types", rf"\btype\s+{IDENTIFIER}(?:\[[^\]]+\])?\s+[A-Za-z_][A-Za-z0-9_]*"),
)

RUST_RULES = rule_set(
    make_rule("Structs", rf"\bstruct\s+{IDENTIFIER}\b"),
    make_rule("Enums", rf"\benum\s+{IDENTIFIER}\b"),
    make_rule("Traits", rf"\btrait\s+{IDENTIFIER}\b"),
    make_rule("Unions", rf"\bunion\s+{IDENTIFIER}\b"),
    make_rule("Type aliases", rf"\btype\s+{IDENTIFIER}(?:<[^>]+>)?\s*="),
    make_rule("Modules", rf"\bmod\s+{IDENTIFIER}\b"),
)

GDSCRIPT_RULES = rule_set(
    make_rule("Classes", rf"^\s*class_name\s+{IDENTIFIER}\b"),
    make_rule("Classes", rf"^\s*class\s+{IDENTIFIER}\b"),
)

PHP_RULES = rule_set(
    make_rule("Enums", rf"\benum\s+{IDENTIFIER}\b"),
    make_rule("Interfaces", rf"\binterface\s+{IDENTIFIER}\b"),
    make_rule("Traits", rf"\btrait\s+{IDENTIFIER}\b"),
    make_rule("Classes", rf"\bclass\s+{IDENTIFIER}\b"),
    make_rule("Namespaces", rf"\bnamespace\s+{IDENTIFIER}(?:\s*\\\s*{IDENTIFIER})*"),
)

SWIFT_RULES = rule_set(
    make_rule("Protocols", rf"\bprotocol\s+{IDENTIFIER}\b"),
    make_rule("Actors", rf"\bactor\s+{IDENTIFIER}\b"),
    make_rule("Structs", rf"\bstruct\s+{IDENTIFIER}\b"),
    make_rule("Enums", rf"\benum\s+{IDENTIFIER}\b"),
    make_rule("Classes", rf"\bclass\s+{IDENTIFIER}\b"),
    make_rule("Extensions", rf"\bextension\s+{IDENTIFIER}\b"),
)

RUBY_RULES = rule_set(
    make_rule("Classes", rf"^\s*class\s+{IDENTIFIER}\b"),
    make_rule("Modules", rf"^\s*module\s+{IDENTIFIER}\b"),
)

POWERSHELL_RULES = rule_set(
    make_rule("Enums", rf"\benum\s+{IDENTIFIER}\b"),
    make_rule("Classes", rf"\bclass\s+{IDENTIFIER}\b"),
)

SQL_RULES = rule_set(
    make_rule(
        "Tables",
        rf"\bCREATE\s+(?:TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{IDENTIFIER}\b",
        re.IGNORECASE,
    ),
    make_rule(
        "Views",
        rf"\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+{IDENTIFIER}\b",
        re.IGNORECASE,
    ),
    make_rule(
        "Functions",
        rf"\bCREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+{IDENTIFIER}\b",
        re.IGNORECASE,
    ),
    make_rule(
        "Procedures",
        rf"\bCREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+{IDENTIFIER}\b",
        re.IGNORECASE,
    ),
    make_rule("Types", rf"\bCREATE\s+TYPE\s+{IDENTIFIER}\b", re.IGNORECASE),
    make_rule("Schemas", rf"\bCREATE\s+SCHEMA\s+{IDENTIFIER}\b", re.IGNORECASE),
)

LANGUAGE_RULES: dict[str, tuple[DeclarationRule, ...]] = {
    ".cs": CS_RULES,
    ".csx": CS_RULES,
    ".c": C_RULES,
    ".asm": ASSEMBLY_RULES,
    ".s": ASSEMBLY_RULES,
    ".inc": ASSEMBLY_RULES,
    ".assembler": ASSEMBLY_RULES,
    ".java": JAVA_RULES,
    ".kt": KOTLIN_RULES,
    ".kts": KOTLIN_RULES,
    ".ts": TYPESCRIPT_RULES,
    ".tsx": TYPESCRIPT_RULES,
    ".js": rule_set(make_rule("Classes", rf"\bclass\s+{IDENTIFIER}\b")),
    ".jsx": rule_set(make_rule("Classes", rf"\bclass\s+{IDENTIFIER}\b")),
    ".py": PYTHON_RULES,
    ".go": GO_RULES,
    ".rs": RUST_RULES,
    ".gd": GDSCRIPT_RULES,
    ".php": PHP_RULES,
    ".swift": SWIFT_RULES,
    ".rb": RUBY_RULES,
    ".ps1": POWERSHELL_RULES,
    ".sql": SQL_RULES,
}

for cpp_extension in {".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"}:
    LANGUAGE_RULES[cpp_extension] = CPP_RULES


# =============================================================================
# Comment and literal masking for declaration analysis
# =============================================================================

C_LIKE_EXTENSIONS = {
    ".cs",
    ".csx",
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".cxx",
    ".hpp",
    ".hh",
    ".hxx",
    ".java",
    ".kt",
    ".kts",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".php",
    ".swift",
}

HASH_COMMENT_EXTENSIONS = {
    ".py",
    ".rb",
    ".sh",
    ".ps1",
    ".bat",
    ".gd",
    ".gdshader",
}

ASSEMBLY_EXTENSIONS = {".asm", ".s", ".inc", ".assembler"}

C_LIKE_NOISE = re.compile(
    r'''
    //[^\x0A]*                       |
    /\*.*?\*/                        |
    @"(?:""|[^"])*"                 |
    "{3}.*?"{3}                      |
    "(?:\\.|[^"\\])*"             |
    '(?:\\.|[^'\\])*'               |
    `(?:\\.|[^`\\])*`
    ''',
    re.DOTALL | re.VERBOSE,
)

HASH_COMMENT_NOISE = re.compile(
    r'''
    \#[^\x0A]*                       |
    '{3}.*?'{3}                        |
    "{3}.*?"{3}                      |
    "(?:\\.|[^"\\])*"             |
    '(?:\\.|[^'\\])*'
    ''',
    re.DOTALL | re.VERBOSE,
)

ASSEMBLY_NOISE = re.compile(
    r'''
    ;[^\x0A]*                        |
    \#[^\x0A]*                       |
    /\*.*?\*/                        |
    "(?:\\.|[^"\\])*"             |
    '(?:\\.|[^'\\])*'
    ''',
    re.DOTALL | re.VERBOSE,
)

SQL_NOISE = re.compile(
    r'''
    --[^\x0A]*                       |
    /\*.*?\*/                        |
    '(?:''|[^'])*'
    ''',
    re.DOTALL | re.VERBOSE,
)

# =============================================================================
# Data types
# =============================================================================

@dataclass(frozen=True)
class SourceFile:
    """A discovered source file and the selected root that supplied it."""

    path: Path
    source_root: Path


@dataclass(frozen=True)
class ExclusionSettings:
    """Directory names and exact paths excluded from recursive scanning."""

    directory_names: frozenset[str]
    directory_paths: frozenset[Path]
    requested_values: tuple[str, ...]


@dataclass(frozen=True)
class GenerationResult:
    """Summary returned after a report has been written successfully."""

    included_files: int
    skipped_files: int
    total_stats: Counter[str]
    files_by_extension: Counter[str]
    generated_at: datetime
    oldest_source: tuple[datetime, SourceFile] | None
    newest_source: tuple[datetime, SourceFile] | None


# =============================================================================
# General helpers
# =============================================================================


def split_option_values(values: Sequence[str] | None) -> list[str]:
    """Split command-line or batch values, allowing semicolon-separated entries."""
    if not values:
        return []

    result: list[str] = []

    for raw_value in values:
        for value in raw_value.split(";"):
            cleaned_value = value.strip().strip('"').strip("'")
            if cleaned_value:
                result.append(cleaned_value)

    return result


def normalize_extensions(values: Sequence[str] | None) -> set[str]:
    """Normalize extension filters so every value starts with a dot."""
    normalized: set[str] = set()

    for value in split_option_values(values):
        extension = value.casefold()

        if not extension.startswith("."):
            extension = f".{extension}"

        normalized.add(extension)

    return normalized


def normalize_folder_path(value: str, base_directory: Path | None = None) -> Path | None:
    """Turn a user-provided path into an absolute normalized path."""
    cleaned_value = value.strip().strip('"').strip("'")

    if not cleaned_value:
        return None

    path = Path(cleaned_value).expanduser()

    if not path.is_absolute():
        path = (base_directory or Path.cwd()) / path

    try:
        return path.resolve()
    except (OSError, RuntimeError):
        return path.absolute()


def validate_folders(raw_paths: Iterable[str]) -> list[Path]:
    """Keep only unique existing directories from supplied values."""
    folders: list[Path] = []
    seen: set[Path] = set()

    for raw_path in raw_paths:
        folder = normalize_folder_path(raw_path)

        if folder is None:
            continue

        if not folder.is_dir():
            print(f"[Skipped: not a directory] {folder}")
            continue

        if folder in seen:
            continue

        seen.add(folder)
        folders.append(folder)

    return folders


def normalize_output_path(value: str, root: Path) -> Path:
    """Resolve an output file path relative to the configured output root."""
    cleaned_value = value.strip().strip('"').strip("'") or "combined_code.txt"
    output_path = Path(cleaned_value).expanduser()

    if not output_path.is_absolute():
        output_path = root / output_path

    try:
        return output_path.resolve()
    except (OSError, RuntimeError):
        return output_path.absolute()


def read_file_safely(file_path: Path) -> str | None:
    """Read a non-binary source file using common project encodings."""
    try:
        raw_data = file_path.read_bytes()
    except OSError as error:
        print(f"[Read error] {file_path}: {error}")
        return None

    if b"\x00" in raw_data:
        print(f"[Skipped binary-looking file] {file_path}")
        return None

    for encoding in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            return raw_data.decode(encoding)
        except UnicodeDecodeError:
            continue

    print(f"[Skipped unknown encoding] {file_path}")
    return None


def format_timestamp(value: datetime) -> str:
    """Return a local timezone-aware timestamp suitable for a text report."""
    return value.astimezone().isoformat(timespec="seconds")


def get_last_modified(file_path: Path) -> datetime | None:
    """Read the filesystem modification time of one file."""
    try:
        return datetime.fromtimestamp(file_path.stat().st_mtime).astimezone()
    except OSError:
        return None


# =============================================================================
# Exclusion handling
# =============================================================================


def looks_like_path(value: str) -> bool:
    """Return True when an exclusion looks like a path instead of a simple name."""
    return "/" in value or "\\" in value or ":" in value or value.startswith("./") or value.startswith(".\\")


def build_exclusion_settings(
    values: Sequence[str] | None,
    source_directories: Sequence[Path],
) -> ExclusionSettings:
    """
    Create exclusion settings from custom names and paths.

    A simple value such as ``vendor`` excludes every directory with that name.
    A relative path such as ``src/generated`` is resolved against every chosen
    source root. Absolute paths are excluded exactly as written.
    """
    directory_names = set(DEFAULT_SKIPPED_DIRECTORY_NAMES)
    directory_paths: set[Path] = set()
    requested_values = split_option_values(values)

    for value in requested_values:
        if not looks_like_path(value):
            directory_names.add(value.casefold())
            continue

        raw_path = Path(value).expanduser()
        candidates: list[Path]

        if raw_path.is_absolute():
            candidates = [raw_path]
        else:
            candidates = [source_root / raw_path for source_root in source_directories]
            candidates.append(Path.cwd() / raw_path)

        for candidate in candidates:
            try:
                directory_paths.add(candidate.resolve())
            except (OSError, RuntimeError):
                directory_paths.add(candidate.absolute())

    return ExclusionSettings(
        directory_names=frozenset(directory_names),
        directory_paths=frozenset(directory_paths),
        requested_values=tuple(requested_values),
    )


def is_excluded_directory(directory: Path, exclusions: ExclusionSettings) -> bool:
    """Return True when a directory matches a default or custom exclusion."""
    if directory.name.casefold() in exclusions.directory_names:
        return True

    try:
        resolved_directory = directory.resolve()
    except (OSError, RuntimeError):
        resolved_directory = directory.absolute()

    for excluded_path in exclusions.directory_paths:
        try:
            if resolved_directory == excluded_path or resolved_directory.is_relative_to(excluded_path):
                return True
        except ValueError:
            continue

    return False


# =============================================================================
# Declaration analysis
# =============================================================================


def mask_keep_newlines(text: str) -> str:
    """Replace text with spaces while preserving line breaks for regex anchors."""
    return "".join("\n" if character == "\n" else " " for character in text)


def strip_non_code(content: str, extension: str) -> str:
    """Mask common comments and literals before declaration matching."""
    if extension in C_LIKE_EXTENSIONS:
        return C_LIKE_NOISE.sub(lambda match: mask_keep_newlines(match.group(0)), content)

    if extension in HASH_COMMENT_EXTENSIONS:
        return HASH_COMMENT_NOISE.sub(lambda match: mask_keep_newlines(match.group(0)), content)

    if extension in ASSEMBLY_EXTENSIONS:
        return ASSEMBLY_NOISE.sub(lambda match: mask_keep_newlines(match.group(0)), content)

    if extension == ".sql":
        return SQL_NOISE.sub(lambda match: mask_keep_newlines(match.group(0)), content)

    return content


def count_declarations(content: str, extension: str) -> Counter[str]:
    """Count language-specific declaration categories using practical regex rules."""
    declaration_rules = LANGUAGE_RULES.get(extension)

    if declaration_rules is None:
        return Counter()

    masked_content = strip_non_code(content, extension)
    result: Counter[str] = Counter()

    for declaration_rule in declaration_rules:
        matches = list(declaration_rule.pattern.finditer(masked_content))

        if not matches:
            continue

        result[declaration_rule.label] += len(matches)

        # Prevent an already matched construct from being counted twice.
        masked_content = declaration_rule.pattern.sub(
            lambda match: mask_keep_newlines(match.group(0)),
            masked_content,
        )

    return result


STAT_ORDER = {
    "Namespaces": 0,
    "Packages": 1,
    "Schemas": 2,
    "Modules": 3,
    "Classes": 10,
    "Records": 11,
    "Structs": 12,
    "Interfaces": 13,
    "Protocols": 14,
    "Traits": 15,
    "Enums": 16,
    "Unions": 17,
    "Delegates": 18,
    "Objects": 19,
    "Actors": 20,
    "Annotations": 21,
    "Concepts": 22,
    "Type aliases": 23,
    "Types": 24,
    "Typedefs": 25,
    "Extensions": 26,
    "Procedures": 27,
    "Macros": 28,
    "Labels": 29,
    "Tables": 30,
    "Views": 31,
    "Functions": 32,
}


def format_stats(stats: Counter[str]) -> str:
    """Format declaration statistics for a file header or project summary."""
    if not stats:
        return "—"

    sorted_items = sorted(
        stats.items(),
        key=lambda item: (STAT_ORDER.get(item[0], 999), item[0].casefold()),
    )

    return ", ".join(f"{label}: {count}" for label, count in sorted_items)


# =============================================================================
# Source discovery
# =============================================================================


def collect_source_files(
    source_directories: Sequence[Path],
    output_path: Path,
    extensions: set[str],
    exclusions: ExclusionSettings,
) -> list[SourceFile]:
    """Recursively collect unique matching files from all chosen source folders."""
    source_files: list[SourceFile] = []
    seen_files: set[Path] = set()

    for source_directory in source_directories:
        for current_directory, directory_names, file_names in os.walk(
            source_directory,
            followlinks=False,
        ):
            current_path = Path(current_directory)

            # Modify os.walk's live directory list so excluded directories are
            # never traversed, rather than merely skipping their files later.
            directory_names[:] = [
                directory_name
                for directory_name in directory_names
                if not is_excluded_directory(current_path / directory_name, exclusions)
            ]

            for file_name in file_names:
                file_path = current_path / file_name

                if file_path.suffix.casefold() not in extensions:
                    continue

                try:
                    resolved_path = file_path.resolve()
                except (OSError, RuntimeError):
                    continue

                # Do not accidentally add the listing itself if it is written
                # inside a selected source directory.
                if resolved_path == output_path:
                    continue

                if resolved_path in seen_files or not resolved_path.is_file():
                    continue

                seen_files.add(resolved_path)
                source_files.append(
                    SourceFile(path=resolved_path, source_root=source_directory)
                )

    return sorted(
        source_files,
        key=lambda source_file: (
            str(source_file.source_root).casefold(),
            str(source_file.path).casefold(),
        ),
    )


def display_file_path(source_file: SourceFile) -> str:
    """Return a readable path relative to the root selected for this file."""
    try:
        return source_file.path.relative_to(source_file.source_root).as_posix()
    except ValueError:
        return str(source_file.path)


# =============================================================================
# Report generation
# =============================================================================


def write_combined_output(
    output_path: Path,
    source_directories: Sequence[Path],
    source_files: Sequence[SourceFile],
    extensions: set[str],
    exclusions: ExclusionSettings,
    include_file_timestamps: bool,
    output_existed: bool,
) -> GenerationResult:
    """
    Write a complete report to a temporary file, then atomically replace target.

    An old report remains intact if reading or writing fails before replacement.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and output_path.is_dir():
        raise IsADirectoryError(f"Output path is a directory: {output_path}")

    total_stats: Counter[str] = Counter()
    files_by_extension: Counter[str] = Counter()
    included_files = 0
    skipped_files = 0
    temporary_path: Path | None = None
    oldest_source: tuple[datetime, SourceFile] | None = None
    newest_source: tuple[datetime, SourceFile] | None = None
    generated_at = datetime.now().astimezone()
    output_action = "UPDATED" if output_existed else "CREATED"

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            delete=False,
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
        ) as output:
            temporary_path = Path(output.name)

            output.write("COMBINED SOURCE CODE\n")
            output.write("=" * 100 + "\n")
            output.write(f"REPORT {output_action} AT: {format_timestamp(generated_at)}\n")
            output.write(
                "SOURCE FILE TIMESTAMPS: "
                f"{'included' if include_file_timestamps else 'not included'}\n"
            )
            output.write("Selected source folders:\n")

            for source_directory in source_directories:
                output.write(f"  {source_directory}\n")

            output.write("Included file extensions:\n")
            output.write("  " + " ".join(sorted(extensions)) + "\n")

            if exclusions.requested_values:
                output.write("Additional excluded directory names or paths:\n")
                for requested_value in exclusions.requested_values:
                    output.write(f"  {requested_value}\n")
            else:
                output.write("Additional excluded directory names or paths: none\n")

            output.write(f"\nFiles found: {len(source_files)}\n\n")

            for source_file in source_files:
                content = read_file_safely(source_file.path)

                if content is None:
                    skipped_files += 1
                    continue

                extension = source_file.path.suffix.casefold()
                file_stats = count_declarations(content, extension)
                visible_path = display_file_path(source_file)
                modified_at = get_last_modified(source_file.path)

                if modified_at is not None:
                    timestamp_entry = (modified_at, source_file)
                    if oldest_source is None or modified_at < oldest_source[0]:
                        oldest_source = timestamp_entry
                    if newest_source is None or modified_at > newest_source[0]:
                        newest_source = timestamp_entry

                total_stats.update(file_stats)
                files_by_extension[extension] += 1
                included_files += 1

                output.write("=" * 100 + "\n")
                output.write(f"SOURCE ROOT: {source_file.source_root}\n")
                output.write(f"FILE: {visible_path}\n")
                if include_file_timestamps:
                    timestamp_text = format_timestamp(modified_at) if modified_at else "unavailable"
                    output.write(f"LAST MODIFIED: {timestamp_text}\n")
                output.write(f"DECLARATIONS: {format_stats(file_stats)}\n")
                output.write("=" * 100 + "\n\n")
                output.write(content.rstrip())
                output.write("\n\n")

            output.write("=" * 100 + "\n")
            output.write("PROJECT STATISTICS\n")
            output.write("=" * 100 + "\n")
            output.write(f"Report generated at: {format_timestamp(generated_at)}\n")
            output.write(f"Files included: {included_files}\n")
            output.write(f"Files skipped: {skipped_files}\n")
            output.write(f"Declarations: {format_stats(total_stats)}\n")

            if include_file_timestamps:
                if oldest_source is not None:
                    output.write(
                        "Oldest included source file: "
                        f"{format_timestamp(oldest_source[0])} | "
                        f"{display_file_path(oldest_source[1])}\n"
                    )
                if newest_source is not None:
                    output.write(
                        "Newest included source file: "
                        f"{format_timestamp(newest_source[0])} | "
                        f"{display_file_path(newest_source[1])}\n"
                    )

            output.write("\nFiles by extension:\n")
            for extension, count in sorted(files_by_extension.items()):
                output.write(f"  {extension}: {count}\n")

        # Path.replace() overwrites the existing report without creating a
        # duplicate name such as "combined_code (1).txt".
        temporary_path.replace(output_path)

    except Exception:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass
        raise

    return GenerationResult(
        included_files=included_files,
        skipped_files=skipped_files,
        total_stats=total_stats,
        files_by_extension=files_by_extension,
        generated_at=generated_at,
        oldest_source=oldest_source,
        newest_source=newest_source,
    )
