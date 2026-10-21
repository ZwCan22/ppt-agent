@echo off
setlocal EnableExtensions DisableDelayedExpansion
title PPT Agent Data Backup
pushd "%~dp0.."
if errorlevel 1 (
    echo [FAIL] Cannot open the project directory.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo [FAIL] Project Python environment was not found.
    popd
    pause
    exit /b 1
)
echo PPT Agent - local data backup
echo Do not run other start/stop commands during a backup.
echo.
".venv\Scripts\python.exe" -u "deploy\backup.py" %*
set "PPT_BACKUP_RESULT=%ERRORLEVEL%"
popd
echo.
pause
exit /b %PPT_BACKUP_RESULT%
