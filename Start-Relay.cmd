@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 (
    echo [Relay] Cannot open the Relay folder.
    pause
    exit /b 1
)

REM Prefer a compatible Python when several versions are installed.
set "PY_RUN="
for %%V in (3.12 3.11 3.13 3.10 3.9) do (
    if not defined PY_RUN (
        py -%%V -c "import sys" >nul 2>&1
        if not errorlevel 1 set "PY_RUN=py -%%V"
    )
)

if not defined PY_RUN (
    python -c "import sys; sys.exit(0 if (3,9) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_RUN=python"
)

if not defined PY_RUN (
    echo.
    echo [Relay] Python 3.9-3.13 was not found.
    echo [Relay] Install Python 3.12 from https://www.python.org/downloads/windows/
    echo [Relay] During setup, enable "Add python.exe to PATH", then try again.
    echo.
    pause
    exit /b 1
)

echo [Relay] Using %PY_RUN%
%PY_RUN% "%~dp0tools\start_relay.py" %*
set "RESULT=%errorlevel%"

if not "%RESULT%"=="0" (
    echo.
    echo [Relay] Could not start. Check the error message above.
    pause
)
exit /b %RESULT%
