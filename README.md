# Code Listing Combiner

A dependency-free Python utility that collects source files from selected project folders into one structured code listing.

It is especially useful for generating source-code appendices for coursework, capstone projects, bachelor's theses, master's theses, and diploma projects. The generated report preserves each file's path and includes declaration statistics where supported.

## Requirements

- Python **3.10+**.
- No third-party Python packages.
- Windows users can launch the tool through `run_code_combiner.bat`.
- The optional folder picker uses Python's built-in `tkinter` module. Manual path entry and command-line folder selection work without it.

## Repository Files

```text
code-combiner/
├── combine_code.py         # Main Python application
├── run_code_combiner.bat   # Windows double-click launcher
├── README.md               # Documentation
└── .gitignore              # Ignores generated reports and Python cache files
```

`run_code_combiner.bat` is part of the utility and should be committed to Git.

Generated reports are local artifacts. The default report folder, `CodeOutput/`, is ignored through `.gitignore`.

## Features

- Select one or more source folders:
  - enter paths manually;
  - choose folders through a Windows folder picker;
  - pass folders through command-line arguments.
- Scan selected folders recursively.
- Combine files into one report with a clear separator and file path before each file.
- Use built-in source-code extensions or provide your own list.
- Skip common build, cache, IDE, dependency, and repository directories.
- Prevent duplicate file entries when selected folders overlap.
- Exclude the generated report itself from scanning.
- Count language-appropriate declarations per file and for the full report.
- Create a new output file when it does not exist.
- Fully replace an existing output file instead of appending a second report or creating a duplicate file name.
- Write through a temporary file first, so an existing report is preserved if generation fails before replacement.

## Quick Start on Windows

The simplest workflow is the batch launcher.

1. Keep `run_code_combiner.bat` next to `combine_code.py`.
2. Double-click `run_code_combiner.bat`.
3. Enter a report name or press Enter to keep the default:

```text
CodeOutput\combined_code.txt
```

4. Choose how to select source folders in the Python menu.
5. Select or enter the project folders to scan.

The batch launcher checks Python in this order:

1. `py -3` through the Windows Python Launcher;
2. `python` from the system `PATH`.

The launcher sends the selected output path to Python through `--output`, so the Python tool will not ask for the output name a second time.

### Example batch-launcher session

```text
================================================================
                    Code Combiner Launcher
================================================================

Enter the output file name or path.
Existing reports are rebuilt and replaced, not appended.

Output file [CodeOutput\combined_code.txt]: CodeOutput\SourceCode_listing.txt

How would you like to select source folders?
1 - Enter paths manually
2 - Select folders in a window
3 - Use both methods
Choice [1]: 1

Folder #1: C:\ExampleProject\src
Folder #2: C:\ExampleProject\tests
Folder #3:
```

## Running the Python Script Directly

Run the interactive mode:

```powershell
python combine_code.py
```

The script asks:

1. how you want to select source folders;
2. which folders to scan;
3. where to write the output report, unless `--output` was already supplied.

### Scan specific folders

```powershell
python combine_code.py --folders "C:\ExampleProject\src" "C:\ExampleProject\tests"
```

### Select folders with a dialog

```powershell
python combine_code.py --choose
```

The dialog supports selecting multiple folders one after another.

### Set the output file name or path

```powershell
python combine_code.py --folders src tests --output CodeOutput\ExampleProject_Code.txt
```

An absolute path is also supported:

```powershell
python combine_code.py --folders src tests --output "C:\Exports\ExampleProject_Code.txt"
```

### Restrict the included file types

For a C# project:

```powershell
python combine_code.py --folders src tests --ext .cs --output CodeOutput\all_csharp_code.txt
```

For a C++ project:

```powershell
python combine_code.py --folders src tests --ext .cpp .hpp .h .c --output CodeOutput\all_cpp_code.txt
```

Extensions may be written with or without the leading dot:

```powershell
python combine_code.py --folders src tests --ext cs --output CodeOutput\all_csharp_code.txt
```

### Combine several project areas

```powershell
python combine_code.py `
  --folders src tests addons tools `
  --ext .cs .gd .gdshader `
  --output CodeOutput\project_code.txt
```

## Command-Line Arguments

| Argument | Description |
| --- | --- |
| `--folders FOLDER [FOLDER ...]` | One or more source folders to scan. |
| `--choose` | Open the folder picker. It can be combined with `--folders`. |
| `--output PATH` | Output file name or path. If it exists, it is rebuilt and replaced. If it does not exist, it is created. |
| `--ext EXTENSION [EXTENSION ...]` | File extensions to include. If omitted, the default extension list is used. |
| `--root PATH` | Base directory for a relative output path. Defaults to the current directory. |
| `--help` | Show built-in command-line help. |

## Output File Behavior

The tool always builds the report from the currently selected source files.

- A missing output file is created.
- An existing output file is updated by replacing its previous contents.
- The tool never appends another report to the end of an existing one.
- It does not create names such as `combined_code (1).txt`.
- The output file is ignored during scanning even if it is located inside a selected source folder.
- The final replacement uses a temporary file in the same directory as the report.

## Default Output Location and Git Ignore

The Windows launcher uses this default output path:

```text
CodeOutput\combined_code.txt
```

The repository `.gitignore` should contain:

```gitignore
# Generated code-combiner reports
CodeOutput/
combined_code.txt

# Python cache files
__pycache__/
*.py[cod]
```

This keeps generated reports out of commits while keeping `run_code_combiner.bat` in the repository.

If you choose another directory for generated reports, add that directory to `.gitignore` as well. For example:

```gitignore
reports/
```

## Default File Extensions

The built-in extension set includes:

```text
.cs  .csx
.c   .h   .cpp  .cc  .cxx  .hpp  .hh  .hxx
.java  .kt  .kts
.js  .jsx  .ts  .tsx
.py  .go  .rs  .gd  .gdshader  .lua  .php  .rb  .swift
.sh  .ps1  .bat  .sql  .html  .css  .scss
```

Use `--ext` when you need only specific languages or want to include an extension that is not part of the default list.

Files with custom extensions can still be included when explicitly listed, but declaration statistics may not be available for them.

## Automatically Skipped Directories

The tool does not enter these directories:

```text
.git
.idea
.vs
.vscode
.godot
.import
.mono
.pytest_cache
__pycache__
bin
obj
node_modules
build
dist
out
```

This avoids collecting repository metadata, IDE configuration, build artifacts, dependencies, and caches.

To customize the list, edit `SKIPPED_DIRECTORIES` near the top of `combine_code.py`.

## Declaration Statistics

Each supported source file receives a declaration summary such as:

```text
DECLARATIONS: Namespaces: 1, Classes: 3, Interfaces: 2, Enums: 1
```

The report also contains a project-wide summary at the end.

| File type | Counted declarations |
| --- | --- |
| C# (`.cs`, `.csx`) | namespaces, classes, records, structs, interfaces, enums, delegates |
| C / C++ | namespaces, classes, structs, enums, unions, concepts, typedefs where applicable |
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

The tool does not count categories that do not exist in a language.

## Report Format

Each file starts with a visible header:

```text
====================================================================================================
SOURCE ROOT: C:\ExampleProject\src
FILE: Core/StateMachines/LayeredStateMachineCore.cs
DECLARATIONS: Namespaces: 1, Classes: 1, Interfaces: 1
====================================================================================================

// Original source content follows here.
```

The end of the report contains a summary:

```text
PROJECT STATISTICS
====================================================================================================
Files included: 84
Files skipped: 0
Declarations: Namespaces: 40, Classes: 91, Interfaces: 26, Enums: 8, Structs: 4

Files by extension:
  .cs: 84
```

## Limitations

Declaration counting uses regular expressions, not language compilers or complete AST parsers.

The script masks common comments and string literals before analysis, which prevents many false positives. Complex language constructs can still affect the counts, including raw strings, source generators, macros, preprocessor output, and unusual multiline declarations.

Use the statistics as a practical overview, not as compiler-verified architecture data.

## Troubleshooting

### `python` is not recognized

Install Python 3.10 or newer and enable the option to add Python to `PATH` during installation.

On Windows, try the Python Launcher:

```powershell
py -3 combine_code.py
```

### The batch launcher cannot find Python

Install Python 3.10 or newer. During setup, enable the Python Launcher and add Python to `PATH`.

The launcher automatically tries `py -3` first and then `python`.

### The folder picker does not open

Use manual mode or provide folders through `--folders`. The picker requires `tkinter`, which may be missing in a minimal Python installation.

### Some files are not included

Check these points:

- the extension is included in the default set or in `--ext`;
- the file is not located in a skipped directory such as `bin`, `obj`, `.git`, or `node_modules`;
- the file is not binary or encoded with an unsupported encoding.

Example with custom extensions:

```powershell
python combine_code.py --folders src tests --ext .cs .shader .txt --output CodeOutput\custom_report.txt
```

### The output file cannot be updated

Close the report in programs that may lock it. On Windows, an editor or viewer can sometimes keep a file open exclusively.

## License

Add a license before publishing the repository. Popular choices include MIT, Apache-2.0, and GPL-3.0.

Until a license is added, people may be able to view the repository but do not automatically receive permission to reuse its code.
