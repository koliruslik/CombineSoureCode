@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Run this launcher from any location. It switches to the folder
rem that contains this .bat file and combine_code.py.
cd /d "%~dp0"

set "SCRIPT_NAME=combine_code.py"
set "DEFAULT_OUTPUT=CodeOutput\combined_code.txt"

if not exist "%SCRIPT_NAME%" (
    echo.
    echo Error: "%SCRIPT_NAME%" was not found in:
    echo %CD%
    echo Place this launcher next to combine_code.py and try again.
    echo.
    pause
    exit /b 1
)

echo ================================================================
echo                     Code Combiner Launcher
echo ================================================================
echo.
echo The source folders will be selected in the Python tool.
echo.
echo Enter the output file name or path.
echo Existing reports are rebuilt and replaced, not appended.
echo.
set /p "OUTPUT_PATH=Output file [%DEFAULT_OUTPUT%]: "

if not defined OUTPUT_PATH set "OUTPUT_PATH=%DEFAULT_OUTPUT%"
set "OUTPUT_PATH=%OUTPUT_PATH:"=%"

rem Prefer the Windows Python Launcher. Fall back to python from PATH.
py -3 --version >nul 2>&1
if not errorlevel 1 (
    py -3 "%SCRIPT_NAME%" --output "%OUTPUT_PATH%"
    set "EXIT_CODE=%ERRORLEVEL%"
    goto :finish
)

python --version >nul 2>&1
if not errorlevel 1 (
    python "%SCRIPT_NAME%" --output "%OUTPUT_PATH%"
    set "EXIT_CODE=%ERRORLEVEL%"
    goto :finish
)

echo.
echo Error: Python 3 was not found.
echo Install Python 3.10 or newer and enable the PATH option during installation.
set "EXIT_CODE=1"

:finish
echo.
if "%EXIT_CODE%"=="0" (
    echo Finished successfully.
) else (
    echo The code combiner stopped with exit code %EXIT_CODE%.
)

echo.
pause
exit /b %EXIT_CODE%
