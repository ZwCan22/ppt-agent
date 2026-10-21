@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0.."
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo [FAIL] Project Python environment was not found.
    popd
    exit /b 1
)
docker compose -p ppt-agent-tests -f deploy\compose.test.yml up -d --wait postgres
if errorlevel 1 (
    echo [FAIL] Test PostgreSQL failed to start.
    popd
    exit /b 1
)
".venv\Scripts\python.exe" -B deploy\check_all.py --frontend
set "PPT_CHECK_RESULT=%ERRORLEVEL%"
popd
exit /b %PPT_CHECK_RESULT%
