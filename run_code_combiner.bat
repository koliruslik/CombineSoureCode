@echo off
setlocal
cd /d "%~dp0"
py -3 combine_code.py
if errorlevel 9009 python combine_code.py
pause
