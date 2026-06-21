@echo off
setlocal EnableExtensions DisableDelayedExpansion

cd /d "%~dp0"

set "SCRIPT=%~dp0combine_code.py"
set "DEFAULT_OUTPUT=CodeOutput\combined_code.txt"

if not exist "%SCRIPT%" (
    echo.
    echo [ERROR] combine_code.py was not found next to this batch file.
    echo Keep run_code_combiner.bat, combine_code.py, and combiner_core.py in the same folder.
    echo.
    pause
    exit /b 1
)

if not exist "%~dp0combiner_core.py" (
    echo.
    echo [ERROR] combiner_core.py was not found next to this batch file.
    echo Keep run_code_combiner.bat, combine_code.py, and combiner_core.py in the same folder.
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo                         Code Listing Combiner
echo ================================================================================
echo.
echo The report will contain its generation time and, by default, the last-modified
echo time of every included source file.
echo.

set /p "OUTPUT_PATH=Output file [%DEFAULT_OUTPUT%]: "
if not defined OUTPUT_PATH set "OUTPUT_PATH=%DEFAULT_OUTPUT%"

echo.
echo Add file formats to the built-in list if needed.
echo Examples: .shader; .proto; .txt
echo Built-in formats already include .sql, .asm, .s, .inc, and .assembler.
set /p "EXTRA_EXTENSIONS=Additional extensions [none]: "

echo.
echo Add directory names or paths that must be skipped.
echo A name such as vendor is skipped anywhere; use semicolons for several entries.
echo Examples: generated; external; source/legacy
set /p "EXCLUDED_DIRECTORIES=Additional exclusions [none]: "

echo.
set /p "TIMESTAMP_CHOICE=Include source-file last-modified timestamps? [Y/n]: "
set "TIMESTAMP_FLAG=--file-timestamps"
if /I "%TIMESTAMP_CHOICE%"=="n" set "TIMESTAMP_FLAG=--no-file-timestamps"
if /I "%TIMESTAMP_CHOICE%"=="no" set "TIMESTAMP_FLAG=--no-file-timestamps"

echo.
echo Starting the Python launcher...
echo.

where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%SCRIPT%" --output "%OUTPUT_PATH%" --add-ext "%EXTRA_EXTENSIONS%" --exclude "%EXCLUDED_DIRECTORIES%" %TIMESTAMP_FLAG%
    if errorlevel 1 goto :python_failed
    set "EXIT_CODE=0"
    goto :finished
)

where python >nul 2>nul
if not errorlevel 1 (
    python "%SCRIPT%" --output "%OUTPUT_PATH%" --add-ext "%EXTRA_EXTENSIONS%" --exclude "%EXCLUDED_DIRECTORIES%" %TIMESTAMP_FLAG%
    if errorlevel 1 goto :python_failed
    set "EXIT_CODE=0"
    goto :finished
)

echo [ERROR] Python 3 was not found.
echo Install Python 3.10 or newer, then enable the Python Launcher or add Python to PATH.
set "EXIT_CODE=1"
goto :finished

:python_failed
set "EXIT_CODE=1"

:finished
echo.
if not "%EXIT_CODE%"=="0" (
    echo The code listing was not generated successfully. Exit code: %EXIT_CODE%
) else (
    echo The code listing was generated successfully.
)
echo.
pause
exit /b %EXIT_CODE%
