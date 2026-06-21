#!/usr/bin/env python3
"""
combine_code.py

Collects source files from one or more directories, writes them into one text
file, and reports common language declarations such as classes, interfaces,
enums, structs, and similar constructs.

The script can be used interactively or through command-line arguments.
Existing output files are rebuilt and replaced; new output files are created.
"""

from __future__ import annotations

import argparse
import os
import re
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Pattern


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_EXTENSIONS = {
    # C#
    ".cs", ".csx",
    # C / C++
    ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx",
    # JVM languages
    ".java", ".kt", ".kts",
    # JavaScript / TypeScript
    ".js", ".jsx", ".ts", ".tsx",
    # Other programming languages
    ".py", ".go", ".rs", ".gd", ".gdshader", ".lua", ".php",
    ".rb", ".swift",
    # Scripts, database, and web files
    ".sh", ".ps1", ".bat", ".sql", ".html", ".css", ".scss",
}

SKIPPED_DIRECTORIES = {
    ".git",
    ".idea",
    ".vs",
    ".vscode",
    ".godot",
    ".import",
    ".mono",
    ".pytest_cache",
    "__pycache__",
    "bin",
    "obj",
    "node_modules",
    "build",
    "dist",
    "out",
}

SKIPPED_DIRECTORY_NAMES = {
    directory.casefold()
    for directory in SKIPPED_DIRECTORIES
}

IDENTIFIER = r"@?[A-Za-z_][A-Za-z0-9_]*"


# =============================================================================
# Declaration rules
# =============================================================================

@dataclass(frozen=True)
class DeclarationRule:
    """A label and a regular expression used to count one declaration type."""

    label: str
    pattern: Pattern[str]


def make_rule(label: str, pattern: str, flags: int = 0) -> DeclarationRule:
    """Create a multiline declaration rule."""
    return DeclarationRule(
        label=label,
        pattern=re.compile(pattern, re.MULTILINE | flags),
    )


def rule_set(*items: DeclarationRule) -> tuple[DeclarationRule, ...]:
    """Make declaration-rule definitions easier to read."""
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
# Comment and string masking for declaration analysis
# =============================================================================

C_LIKE_EXTENSIONS = {
    ".cs", ".csx", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh",
    ".hxx", ".java", ".kt", ".kts", ".js", ".jsx", ".ts", ".tsx", ".go",
    ".rs", ".php", ".swift",
}

HASH_COMMENT_EXTENSIONS = {".py", ".rb", ".sh", ".ps1", ".bat", ".gd", ".gdshader"}

C_LIKE_NOISE = re.compile(
    r'''
    //[^\n]*                           |
    /\*.*?\*/                          |
    @?"(?:""|[^"\\])*"               |
    "{3}.*?"{3}                        |
    "(?:\\.|[^"\\])*"               |
    '(?:\\.|[^'\\])*'                 |
    `(?:\\.|[^`\\])*`
    ''',
    re.DOTALL | re.VERBOSE,
)

HASH_COMMENT_NOISE = re.compile(
    r'''
    \#[^\n]*                           |
    '{3}.*?'{3}                        |
    "{3}.*?"{3}                        |
    "(?:\\.|[^"\\])*"               |
    '(?:\\.|[^'\\])*'
    ''',
    re.DOTALL | re.VERBOSE,
)

SQL_NOISE = re.compile(
    r'''
    --[^\n]*                           |
    /\*.*?\*/                          |
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


# =============================================================================
# File and analysis helpers
# =============================================================================

def should_skip(relative_path: Path) -> bool:
    """Return True when any part of a path is a configured ignored directory."""
    return any(
        path_part.casefold() in SKIPPED_DIRECTORY_NAMES
        for path_part in relative_path.parts
    )


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


def normalize_extensions(values: list[str] | None) -> set[str]:
    """Return normalized extension filters, including the leading dot."""
    if not values:
        return set(DEFAULT_EXTENSIONS)

    normalized: set[str] = set()

    for value in values:
        cleaned_value = value.strip().lower()

        if not cleaned_value:
            continue

        if not cleaned_value.startswith("."):
            cleaned_value = f".{cleaned_value}"

        normalized.add(cleaned_value)

    return normalized


def mask_keep_newlines(text: str) -> str:
    """Replace text with spaces while preserving line breaks for regex anchors."""
    return "".join("\n" if character == "\n" else " " for character in text)


def strip_non_code(content: str, extension: str) -> str:
    """Mask common comments and literals before declaration matching."""
    if extension in C_LIKE_EXTENSIONS:
        return C_LIKE_NOISE.sub(lambda match: mask_keep_newlines(match.group(0)), content)

    if extension in HASH_COMMENT_EXTENSIONS:
        return HASH_COMMENT_NOISE.sub(lambda match: mask_keep_newlines(match.group(0)), content)

    if extension == ".sql":
        return SQL_NOISE.sub(lambda match: mask_keep_newlines(match.group(0)), content)

    return content


def count_declarations(content: str, extension: str) -> Counter[str]:
    """Count declaration categories supported for the file's language."""
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

        # Mask already counted declarations. This prevents, for example,
        # "record class User" from being counted as both Record and Class.
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
    "Tables": 30,
    "Views": 31,
    "Functions": 32,
    "Procedures": 33,
}


def format_stats(stats: Counter[str]) -> str:
    """Format declaration statistics for the combined output and terminal."""
    if not stats:
        return "—"

    sorted_items = sorted(
        stats.items(),
        key=lambda item: (STAT_ORDER.get(item[0], 999), item[0].casefold()),
    )

    return ", ".join(f"{label}: {count}" for label, count in sorted_items)


# =============================================================================
# Folder selection
# =============================================================================

def normalize_folder_path(value: str) -> Path | None:
    """Turn a user-provided folder string into an absolute path."""
    cleaned_value = value.strip().strip('"').strip("'")

    if not cleaned_value:
        return None

    path = Path(cleaned_value).expanduser()

    if not path.is_absolute():
        path = Path.cwd() / path

    try:
        return path.resolve()
    except (OSError, RuntimeError):
        return path.absolute()


def validate_folders(raw_paths: list[str]) -> list[Path]:
    """Keep only unique, existing directories from user input."""
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


def split_manual_paths(raw_value: str) -> list[str]:
    """Allow several manually entered paths separated by semicolons."""
    return [value.strip() for value in raw_value.split(";") if value.strip()]


def enter_folders_manually() -> list[Path]:
    """Ask for one or more folder paths in the console."""
    print()
    print("Enter source folders one at a time.")
    print("You may enter multiple paths separated with a semicolon (;).")
    print("Submit an empty line when you are finished.")
    print()

    raw_paths: list[str] = []
    folder_number = 1

    while True:
        try:
            raw_value = input(f"Folder #{folder_number}: ").strip()
        except EOFError:
            break

        if not raw_value:
            break

        values_from_line = split_manual_paths(raw_value)
        raw_paths.extend(values_from_line)
        folder_number += len(values_from_line)

    return validate_folders(raw_paths)


def choose_folders_from_dialog() -> list[Path]:
    """Open the native folder-picker dialog and allow repeated selection."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox

        app = tk.Tk()
        app.withdraw()
        app.attributes("-topmost", True)
    except Exception as error:
        print(f"Could not open the folder picker: {error}")
        print("Use manual path input instead.")
        return []

    selected_paths: list[str] = []

    try:
        while True:
            selected_path = filedialog.askdirectory(
                parent=app,
                title="Select a source folder",
                mustexist=True,
            )

            if not selected_path:
                break

            selected_paths.append(selected_path)

            add_more = messagebox.askyesno(
                title="Add another folder?",
                message="Do you want to add another source folder?",
                parent=app,
            )

            if not add_more:
                break
    finally:
        app.destroy()

    return validate_folders(selected_paths)


def get_source_directories(args: argparse.Namespace) -> list[Path]:
    """Resolve source directories from command-line and interactive choices."""
    folders: list[Path] = []

    if args.folders:
        folders.extend(validate_folders(args.folders))

    if args.choose:
        folders.extend(choose_folders_from_dialog())

    if not args.folders and not args.choose:
        print("How would you like to select source folders?")
        print("1 — Enter paths manually")
        print("2 — Select folders in a window")
        print("3 — Use both methods")

        try:
            choice = input("Choice [1]: ").strip() or "1"
        except EOFError:
            choice = "1"

        if choice not in {"1", "2", "3"}:
            print("Unknown choice. Manual input will be used.")
            choice = "1"

        if choice in {"1", "3"}:
            folders.extend(enter_folders_manually())

        if choice in {"2", "3"}:
            folders.extend(choose_folders_from_dialog())

    unique_folders: list[Path] = []
    seen: set[Path] = set()

    for folder in folders:
        if folder not in seen:
            seen.add(folder)
            unique_folders.append(folder)

    return unique_folders


# =============================================================================
# Output path selection
# =============================================================================

def normalize_output_path(value: str, root: Path) -> Path:
    """Resolve an output file path relative to the selected output root."""
    cleaned_value = value.strip().strip('"').strip("'")

    if not cleaned_value:
        cleaned_value = "combined_code.txt"

    output_path = Path(cleaned_value).expanduser()

    if not output_path.is_absolute():
        output_path = root / output_path

    try:
        return output_path.resolve()
    except (OSError, RuntimeError):
        return output_path.absolute()


def get_output_path(args: argparse.Namespace, root: Path) -> Path:
    """Use --output when supplied; otherwise ask the user for a file name."""
    if args.output:
        return normalize_output_path(args.output, root)

    print()
    print("Choose the output file name or path.")
    print("If the file already exists, it will be fully updated (replaced).")

    try:
        raw_value = input("Output file [combined_code.txt]: ").strip()
    except EOFError:
        raw_value = ""

    return normalize_output_path(raw_value or "combined_code.txt", root)


# =============================================================================
# Source file discovery
# =============================================================================

def collect_source_files(
    source_directories: list[Path],
    output_path: Path,
    extensions: set[str],
) -> list[SourceFile]:
    """Recursively collect unique code files from all chosen source folders."""
    source_files: list[SourceFile] = []
    seen_files: set[Path] = set()

    for source_directory in source_directories:
        for current_directory, directory_names, file_names in os.walk(
            source_directory,
            followlinks=False,
        ):
            # Prevent os.walk from descending into ignored directories.
            directory_names[:] = [
                directory_name
                for directory_name in directory_names
                if directory_name.casefold() not in SKIPPED_DIRECTORY_NAMES
            ]

            current_path = Path(current_directory)

            for file_name in file_names:
                file_path = current_path / file_name

                try:
                    relative_path = file_path.relative_to(source_directory)
                except ValueError:
                    continue

                if should_skip(relative_path):
                    continue

                if file_path.suffix.lower() not in extensions:
                    continue

                try:
                    resolved_path = file_path.resolve()
                except (OSError, RuntimeError):
                    continue

                # This protects against scanning the output file when it is
                # stored inside one of the chosen source directories.
                if resolved_path == output_path:
                    continue

                if resolved_path in seen_files:
                    continue

                if not resolved_path.is_file():
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
    """Return a readable path relative to the source root when possible."""
    try:
        relative_path = source_file.path.relative_to(source_file.source_root)
        return relative_path.as_posix()
    except ValueError:
        return str(source_file.path)


# =============================================================================
# Combined output generation
# =============================================================================

def write_combined_output(
    output_path: Path,
    source_directories: list[Path],
    source_files: list[SourceFile],
) -> tuple[int, int, Counter[str], Counter[str]]:
    """
    Write the combined code report to a temporary file and atomically replace
    the target file. Returns included-file count, skipped-file count, total
    declaration statistics, and file counts by extension.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and output_path.is_dir():
        raise IsADirectoryError(f"Output path is a directory: {output_path}")

    total_stats: Counter[str] = Counter()
    files_by_extension: Counter[str] = Counter()
    included_files = 0
    skipped_files = 0
    temporary_path: Path | None = None

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
            output.write("Selected source folders:\n")

            for source_directory in source_directories:
                output.write(f"  {source_directory}\n")

            output.write(f"\nFiles found: {len(source_files)}\n\n")

            for source_file in source_files:
                content = read_file_safely(source_file.path)

                if content is None:
                    skipped_files += 1
                    continue

                extension = source_file.path.suffix.lower()
                file_stats = count_declarations(content, extension)
                visible_path = display_file_path(source_file)

                total_stats.update(file_stats)
                files_by_extension[extension] += 1
                included_files += 1

                output.write("=" * 100 + "\n")
                output.write(f"SOURCE ROOT: {source_file.source_root}\n")
                output.write(f"FILE: {visible_path}\n")
                output.write(f"DECLARATIONS: {format_stats(file_stats)}\n")
                output.write("=" * 100 + "\n\n")
                output.write(content.rstrip())
                output.write("\n\n")

            output.write("=" * 100 + "\n")
            output.write("PROJECT STATISTICS\n")
            output.write("=" * 100 + "\n")
            output.write(f"Files included: {included_files}\n")
            output.write(f"Files skipped: {skipped_files}\n")
            output.write(f"Declarations: {format_stats(total_stats)}\n\n")
            output.write("Files by extension:\n")

            for extension, count in sorted(files_by_extension.items()):
                output.write(f"  {extension}: {count}\n")

        # Path.replace() replaces an existing output file instead of creating
        # a second file with a different name. The temporary file also protects
        # the old report if an error occurs while collecting source content.
        temporary_path.replace(output_path)

    except Exception:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass
        raise

    return included_files, skipped_files, total_stats, files_by_extension


# =============================================================================
# Command-line entry point
# =============================================================================

def create_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line interface definition."""
    parser = argparse.ArgumentParser(
        description=(
            "Combine source files from selected folders into one text file "
            "and report common declarations."
        ),
    )

    parser.add_argument(
        "--root",
        default=".",
        help=(
            "Base directory used for relative output paths. "
            "Defaults to the current directory."
        ),
    )

    parser.add_argument(
        "--output",
        help=(
            "Output file name or path. If omitted, the script asks for it. "
            "An existing file is updated; a missing file is created."
        ),
    )

    parser.add_argument(
        "--ext",
        nargs="*",
        metavar="EXTENSION",
        help=(
            "File extensions to include, for example: --ext .cs .cpp .hpp. "
            "When omitted, the built-in extension list is used."
        ),
    )

    parser.add_argument(
        "--folders",
        nargs="+",
        metavar="FOLDER",
        help=(
            "One or more source folders to scan, for example: "
            "--folders src tests addons"
        ),
    )

    parser.add_argument(
        "--choose",
        action="store_true",
        help="Open the native folder picker and select source folders.",
    )

    return parser


def main() -> None:
    """Run the interactive or command-line source combiner."""
    parser = create_argument_parser()
    args = parser.parse_args()

    root = Path(args.root).expanduser()

    try:
        root = root.resolve()
    except (OSError, RuntimeError):
        root = root.absolute()

    source_directories = get_source_directories(args)

    if not source_directories:
        print("No valid source folders were selected.")
        return

    output_path = get_output_path(args, root)
    extensions = normalize_extensions(args.ext)

    output_existed = output_path.exists()

    try:
        source_files = collect_source_files(
            source_directories=source_directories,
            output_path=output_path,
            extensions=extensions,
        )
    except OSError as error:
        print(f"Could not scan source folders: {error}")
        return

    if not source_files:
        print("No files matching the selected extensions were found.")
        return

    try:
        included_files, skipped_files, total_stats, _ = write_combined_output(
            output_path=output_path,
            source_directories=source_directories,
            source_files=source_files,
        )
    except OSError as error:
        print(f"Could not write the output file: {error}")
        return

    action = "updated" if output_existed else "created"

    print()
    print(f"Done. Included files: {included_files}")
    print(f"Skipped files: {skipped_files}")
    print(f"Declarations: {format_stats(total_stats)}")
    print(f"Output file {action}: {output_path}")


if __name__ == "__main__":
    main()
