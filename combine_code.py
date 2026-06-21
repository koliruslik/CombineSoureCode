#!/usr/bin/env python3
"""
Command-line and interactive launcher for the Code Listing Combiner.

The launcher gathers user choices and delegates scanning, statistics, and output
replacement to combiner_core.py.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from combiner_core import (
    DEFAULT_EXTENSIONS,
    build_exclusion_settings,
    collect_source_files,
    format_stats,
    normalize_extensions,
    normalize_output_path,
    split_option_values,
    validate_folders,
    write_combined_output,
)


# =============================================================================
# Interactive input helpers
# =============================================================================


def split_manual_paths(raw_value: str) -> list[str]:
    """Allow several source-folder paths separated by semicolons."""
    return split_option_values([raw_value])


def enter_folders_manually() -> list[Path]:
    """Ask for one or more source-folder paths in the terminal."""
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
    """Open the native folder picker and allow repeated selection."""
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


def get_source_directories(args: argparse.Namespace) -> tuple[list[Path], bool]:
    """Resolve source roots and report whether the user is in interactive mode."""
    folders: list[Path] = []
    interactive_mode = not args.folders and not args.choose

    if args.folders:
        folders.extend(validate_folders(args.folders))

    if args.choose:
        folders.extend(choose_folders_from_dialog())

    if interactive_mode:
        print("How would you like to select source folders?")
        print("1 - Enter paths manually")
        print("2 - Select folders in a window")
        print("3 - Use both methods")

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

    return unique_folders, interactive_mode


def get_output_path(args: argparse.Namespace, root: Path) -> Path:
    """Use --output when supplied; otherwise request an output file path."""
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


def prompt_additional_extensions() -> list[str]:
    """Ask for optional formats that should be added to default extensions."""
    print()
    print("Additional file extensions to include (optional).")
    print("Example: .shader; .txt; .proto")

    try:
        raw_value = input("Additional extensions [none]: ").strip()
    except EOFError:
        raw_value = ""

    return split_option_values([raw_value])


def prompt_exclusions() -> list[str]:
    """Ask for optional directory names or paths that should be skipped."""
    print()
    print("Additional folder names or paths to exclude (optional).")
    print("A name such as vendor excludes it at every depth.")
    print("Example: generated; external; source/legacy")

    try:
        raw_value = input("Additional exclusions [none]: ").strip()
    except EOFError:
        raw_value = ""

    return split_option_values([raw_value])


def prompt_file_timestamps() -> bool:
    """Ask whether every report entry should include its last-modified time."""
    print()
    try:
        answer = input("Include last-modified timestamps for source files? [Y/n]: ").strip()
    except EOFError:
        answer = ""

    return answer.casefold() not in {"n", "no"}


# =============================================================================
# Argument parsing and option resolution
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
        "--folders",
        nargs="+",
        metavar="FOLDER",
        help=(
            "One or more source folders to scan, for example: "
            "--folders src tests tools"
        ),
    )

    parser.add_argument(
        "--choose",
        action="store_true",
        help="Open the native folder picker and select source folders.",
    )

    parser.add_argument(
        "--ext",
        nargs="*",
        metavar="EXTENSION",
        help=(
            "Use only these extensions. Values may be separated by spaces or "
            "semicolons, for example: --ext .cs .cpp .hpp"
        ),
    )

    parser.add_argument(
        "--add-ext",
        nargs="*",
        metavar="EXTENSION",
        help=(
            "Add extensions to the built-in list. Values may be separated by "
            "spaces or semicolons, for example: --add-ext .shader;.proto"
        ),
    )

    parser.add_argument(
        "--exclude",
        nargs="*",
        metavar="DIRECTORY",
        help=(
            "Add directory names or paths to skip. A simple name is skipped at "
            "every depth; a relative path is resolved from selected roots."
        ),
    )

    timestamp_group = parser.add_mutually_exclusive_group()
    timestamp_group.add_argument(
        "--file-timestamps",
        dest="include_file_timestamps",
        action="store_true",
        help="Include a last-modified timestamp for every source file.",
    )
    timestamp_group.add_argument(
        "--no-file-timestamps",
        dest="include_file_timestamps",
        action="store_false",
        help="Do not include per-file last-modified timestamps in the report.",
    )
    parser.set_defaults(include_file_timestamps=None)

    return parser


def resolve_extensions(args: argparse.Namespace, interactive_mode: bool) -> set[str]:
    """Resolve default, replacement, and additional extension filters."""
    if args.ext is not None:
        extensions = normalize_extensions(args.ext)
    else:
        extensions = set(DEFAULT_EXTENSIONS)

    if interactive_mode and args.ext is None and args.add_ext is None:
        additional_values = prompt_additional_extensions()
    else:
        additional_values = args.add_ext

    extensions.update(normalize_extensions(additional_values))
    return extensions


def resolve_exclusions(
    args: argparse.Namespace,
    source_directories: Sequence[Path],
    interactive_mode: bool,
):
    """Resolve default and user-supplied directory exclusions."""
    if interactive_mode and args.exclude is None:
        raw_values = prompt_exclusions()
    else:
        raw_values = args.exclude

    return build_exclusion_settings(raw_values, source_directories)


def resolve_file_timestamps(args: argparse.Namespace, interactive_mode: bool) -> bool:
    """Use CLI preference, interactive preference, or the default of True."""
    if args.include_file_timestamps is not None:
        return args.include_file_timestamps

    if interactive_mode:
        return prompt_file_timestamps()

    return True


# =============================================================================
# Entry point
# =============================================================================


def main() -> int:
    """Run the source-code combiner."""
    parser = create_argument_parser()
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    try:
        root = root.resolve()
    except (OSError, RuntimeError):
        root = root.absolute()

    source_directories, interactive_mode = get_source_directories(args)

    if not source_directories:
        print("No valid source folders were selected.")
        return 1

    output_path = get_output_path(args, root)
    extensions = resolve_extensions(args, interactive_mode)
    exclusions = resolve_exclusions(args, source_directories, interactive_mode)
    include_file_timestamps = resolve_file_timestamps(args, interactive_mode)
    output_existed = output_path.exists()

    try:
        source_files = collect_source_files(
            source_directories=source_directories,
            output_path=output_path,
            extensions=extensions,
            exclusions=exclusions,
        )
    except OSError as error:
        print(f"Could not scan source folders: {error}")
        return 1

    if not source_files:
        print("No files matching the selected extensions were found.")
        return 1

    try:
        result = write_combined_output(
            output_path=output_path,
            source_directories=source_directories,
            source_files=source_files,
            extensions=extensions,
            exclusions=exclusions,
            include_file_timestamps=include_file_timestamps,
            output_existed=output_existed,
        )
    except OSError as error:
        print(f"Could not write the output file: {error}")
        return 1

    action = "updated" if output_existed else "created"

    print()
    print(f"Done. Included files: {result.included_files}")
    print(f"Skipped files: {result.skipped_files}")
    print(f"Declarations: {format_stats(result.total_stats)}")
    print(f"Report generated at: {result.generated_at.astimezone().isoformat(timespec='seconds')}")
    print(f"Output file {action}: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
