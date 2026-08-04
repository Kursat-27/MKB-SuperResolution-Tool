@echo off
setlocal enabledelayedexpansion

cd /d "C:\Users\Kürşat\Documents\antigravity\SuperResolutionApp"

if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Starting MKB Super Resolution Tool (v7.0 Fujifilm Color Science)...
"%PYTHON_EXE%" app_gui.py
if errorlevel 1 (
    echo.
    echo Application exited with an error. Press any key to exit...
    pause >nul
)
