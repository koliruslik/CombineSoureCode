# Code Listing Combiner

A dependency-free Python utility that collects source files from selected folders and writes them into one structured code listing.

It is especially useful for generating source-code appendices for coursework, capstone projects, bachelor's theses, master's theses, and diploma projects. Each generated report preserves source paths, records when the report was built, shows when each source file was last modified, and includes declaration statistics where supported.

## Requirements

- Python **3.10+**.
- No third-party Python packages.
- Windows users can launch the tool through `run_code_combiner.bat`.
- The optional folder picker uses Python's built-in `tkinter` module. Manual path input and command-line folder selection work without it.

## Repository Structure

```text
code-listing-combiner/
├── combine_code.py         # CLI and interactive launcher
├── combiner_core.py        # Scanning, filtering, statistics, and report engine
├── run_code_combiner.bat   # Windows double-click launcher
├── README.md               # Documentation
└── .gitignore              # Ignores generated reports and Python cache files
```

Keep `combine_code.py` and `combiner_core.py` in the same directory. The first file collects command-line and interactive choices; the second file performs source discovery, filtering, declaration analysis, timestamp collection, and safe report replacement.

`run_code_combiner.bat` is part of the utility and should be committed to Git. Generated reports are local artifacts; the default `CodeOutput/` directory is ignored through `.gitignore`.

## Features

- Select one or more source folders manually, through a folder picker, or with CLI arguments.
- Scan every selected folder recursively.
- Combine different programming languages into one report.
- Support built-in source extensions, including SQL and assembly files.
- Add any extra file extension without modifying Python code.
- Exclude extra dependency, generated, legacy, or vendor folders by name or path.
- Skip common build output, cache, IDE metadata, dependency, and third-party directories by default.
- Prevent duplicate file entries when selected folders overlap.
- Exclude the generated report itself from scanning.
- Create a missing output file or safely replace an existing output file.
- Write to a temporary file before replacement, so a previous report survives a failed generation.
- Include a report generation timestamp and optional last-modified timestamps for every included source file.
- Count language-appropriate declarations per file and for the overall report.

## Quick Start on Windows

The simplest workflow is the batch launcher.

1. Keep `run_code_combiner.bat`, `combine_code.py`, and `combiner_core.py` together.
2. Double-click `run_code_combiner.bat`.
3. Enter an output file name or press Enter to use the default:

```text
CodeOutput\combined_code.txt
```

4. Optionally enter extra extensions to add to the built-in list.
5. Optionally enter directory names or paths to skip.
6. Choose whether to include source-file timestamps.
7. Choose source folders in the Python menu.

The batch launcher tries Python in this order:

1. `py -3` through the Windows Python Launcher;
2. `python` from the system `PATH`.

### Example batch-launcher session

```text
================================================================================
                         Code Listing Combiner
================================================================================

Output file [CodeOutput\combined_code.txt]: CodeOutput\source_listing.txt
Additional extensions [none]: .proto; .shader
Additional exclusions [none]: vendor; generated; source/legacy
Include source-file last-modified timestamps? [Y/n]: Y

How would you like to select source folders?
1 - Enter paths manually
2 - Select folders in a window
3 - Use both methods
Choice [1]: 1

Folder #1: C:\SampleProject\src
Folder #2: C:\SampleProject\tests
Folder #3:
```

## Running the Python Script Directly

### Interactive mode

```powershell
python combine_code.py
```

Interactive mode asks for source folders, an output path, optional additional extensions, optional exclusions, and whether per-file timestamps should be shown.

### Scan selected folders

```powershell
python combine_code.py --folders "C:\SampleProject\src" "C:\SampleProject\tests" --output CodeOutput\source_listing.txt
```

### Choose folders in a dialog

```powershell
python combine_code.py --choose --output CodeOutput\source_listing.txt
```

The dialog supports selecting multiple folders one after another.

### Combine several project areas

```powershell
python combine_code.py `
  --folders src tests tools `
  --output CodeOutput\project_listing.txt
```

### Use only specific formats

`--ext` replaces the default extension list.

```powershell
python combine_code.py --folders src tests --ext .cs .sql .asm --output CodeOutput\selected_formats.txt
```

Extensions may be written with or without a leading dot:

```powershell
python combine_code.py --folders src tests --ext cs sql asm --output CodeOutput\selected_formats.txt
```

### Add formats without replacing defaults

`--add-ext` preserves all built-in formats and adds the requested ones.

```powershell
python combine_code.py --folders src tests --add-ext .proto .shader .txt --output CodeOutput\extended_listing.txt
```

A semicolon-separated form also works and is convenient for the batch launcher:

```powershell
python combine_code.py --folders src tests --add-ext ".proto; .shader; .txt" --output CodeOutput\extended_listing.txt
```

### Exclude extra folders

A simple directory name is ignored anywhere below every selected source root:

```powershell
python combine_code.py --folders src tests --exclude vendor generated external --output CodeOutput\clean_listing.txt
```

A relative directory path is resolved from each selected source root:

```powershell
python combine_code.py --folders "C:\SampleProject" --exclude "source/legacy" --output CodeOutput\clean_listing.txt
```

Several exclusions may be provided as one semicolon-separated value:

```powershell
python combine_code.py --folders src tests --exclude "vendor; generated; source/legacy" --output CodeOutput\clean_listing.txt
```

### Control source-file timestamps

Per-file timestamps are enabled by default in interactive mode and when no timestamp flag is supplied in CLI mode.

```powershell
python combine_code.py --folders src tests --file-timestamps --output CodeOutput\dated_listing.txt
python combine_code.py --folders src tests --no-file-timestamps --output CodeOutput\compact_listing.txt
```

## Command-Line Arguments

| Argument | Description |
| --- | --- |
| `--folders FOLDER [FOLDER ...]` | One or more source folders to scan. |
| `--choose` | Open the folder picker. It can be combined with `--folders`. |
| `--output PATH` | Output file name or path. An existing file is replaced; a missing file is created. |
| `--ext EXTENSION [EXTENSION ...]` | Use only the supplied formats, replacing the default extension list. |
| `--add-ext EXTENSION [EXTENSION ...]` | Add formats to the default extension list. |
| `--exclude DIRECTORY [DIRECTORY ...]` | Add directory names or paths to skip. Simple names match at any depth. |
| `--file-timestamps` | Include a last-modified timestamp for each source file. |
| `--no-file-timestamps` | Hide per-file last-modified timestamps. |
| `--root PATH` | Base directory for a relative output path. Defaults to the current directory. |
| `--help` | Show built-in command-line help. |

## Output File and Timestamp Behavior

The tool always builds a fresh report from the currently selected source files.

- A missing output file is created.
- An existing output file is fully updated by replacing its previous contents.
- The tool never appends another report or creates names such as `combined_code (1).txt`.
- The report header contains `REPORT CREATED AT` or `REPORT UPDATED AT` with a local timezone-aware timestamp.
- Each source entry contains `LAST MODIFIED` by default.
- The end of the report shows the oldest and newest included source file when per-file timestamps are enabled.
- The generated output file is ignored during scanning even when it is inside a selected source folder.
- The report is generated in a temporary file in the same directory and replaces the old report only after generation succeeds.

Example file header:

```text
====================================================================================================
SOURCE ROOT: C:\SampleProject\src
FILE: Core/Processor.cs
LAST MODIFIED: 2026-06-21T18:30:00+03:00
DECLARATIONS: Namespaces: 1, Classes: 2, Interfaces: 1
====================================================================================================
```

## Default File Extensions

The built-in extension set includes:

```text
.cs  .csx
.c   .h   .cpp  .cc  .cxx  .hpp  .hh  .hxx
.asm  .s  .inc  .assembler
.java  .kt  .kts
.js  .jsx  .ts  .tsx
.py  .go  .rs  .gd  .gdshader  .lua  .php  .rb  .swift
.sh  .ps1  .bat  .sql  .html  .css  .scss
```

Assembly files are included by default. Their approximate declaration summary may contain `Labels`, `Macros`, and MASM-style `Procedures`; they do not have object-oriented categories such as classes or interfaces.

Use `--add-ext` for extra formats or `--ext` when you want a strict allowlist.

## Default Skipped Directories

The tool skips these directories by default:

```text
.git              .idea          .vs             .vscode
.godot            .import        .mono           .pytest_cache
__pycache__       .venv          venv            site-packages
bin               obj            build           dist
out               target         node_modules    packages
package_cache     external       third_party     third-party
vendor            vendors        libs            libraries
```

This keeps repository metadata, IDE configuration, build artifacts, caches, package folders, and typical bundled third-party code out of the report. Use `--exclude` or the batch-launcher exclusion prompt to add project-specific names or paths.

## Declaration Statistics

Each supported source file receives a declaration summary. The full report contains combined statistics at the end.

| File type | Counted declarations |
| --- | --- |
| C# (`.cs`, `.csx`) | namespaces, classes, records, structs, interfaces, enums, delegates |
| C / C++ | namespaces, classes, structs, enums, unions, concepts, typedefs where applicable |
| Assembly (`.asm`, `.s`, `.inc`, `.assembler`) | labels, macros, MASM-style procedures |
| Java | packages, classes, records, interfaces, enums, annotation interfaces |
| Kotlin | classes, interfaces, enums, objects, annotations, type aliases |
| TypeScript | classes, interfaces, enums, type aliases, namespaces/modules |
| JavaScript | classes |
| Python | classes |
| Go | interfaces, structs, type aliases, types |
| Rust | structs, enums, traits, unions, modules, type aliases |
| GDScript | `class_name` declarations and nested classes |
| PHP | namespaces, classes, interfaces, traits, enums |
| Swift | classes, structs, enums, protocols, actors, extensions |
| Ruby | classes, modules |
| PowerShell | classes, enums |
| SQL | schemas, tables, views, functions, procedures, types |

The tool does not count categories that do not exist in a language. It can include arbitrary extra formats in the listing, but declaration statistics are available only for supported languages.

## Limitations

Declaration counting uses regular expressions, not language compilers or complete AST parsers. The tool masks common comments and string literals before analysis, which prevents many false positives, but complex language constructs can still affect counts.

Use the statistics as a practical overview, not as compiler-verified architecture data.

## Troubleshooting

### `python` is not recognized

Install Python 3.10 or newer and enable the option to add Python to `PATH` during installation. On Windows, try the Python Launcher:

```powershell
py -3 combine_code.py
```

### The batch launcher cannot find Python

Install Python 3.10 or newer. During setup, enable the Python Launcher and add Python to `PATH`.

### The folder picker does not open

Use manual mode or provide folders through `--folders`. The picker requires `tkinter`, which can be absent in minimal Python installations.

### Some files are not included

Check these points:

- the extension is part of the default list or was supplied through `--add-ext` or `--ext`;
- the file is not in a default skipped directory;
- no custom `--exclude` rule matches the file's parent directory;
- the file is not binary and uses a supported encoding (`UTF-8`, UTF-8 with BOM, or CP1251).

### The output file cannot be updated

Close the report in any application that may lock it. On Windows, an editor or viewer can sometimes keep a file open exclusively.

## License

Add a license before publishing the repository. Popular choices include MIT, Apache-2.0, and GPL-3.0. Until a license is added, people may be able to view the repository but do not automatically receive permission to reuse its code.
