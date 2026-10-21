@echo off
setlocal EnableExtensions DisableDelayedExpansion
title PPT Agent Startup
set "PPT_START_RESULT=1"

pushd "%~dp0.."
if errorlevel 1 (
    echo [FAIL] Cannot open the project directory.
    pause
    exit /b 1
)

echo ==================================================
echo PPT Agent - start services and check readiness
echo ==================================================
echo.

if not exist "deploy\.env" (
    echo [FAIL] Missing deploy\.env.
    goto finish
)
if not exist "backend\.env" (
    echo [FAIL] Missing backend\.env.
    goto finish
)

where docker >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Docker CLI was not found. Check Docker Desktop installation.
    goto finish
)
where curl.exe >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Windows curl.exe was not found.
    goto finish
)
call docker info --format "{{.ServerVersion}}" >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Docker Engine is not ready. Start Docker Desktop first.
    goto finish
)
call docker compose version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Docker Compose is unavailable.
    goto finish
)
call docker compose --env-file "deploy\.env" -f "deploy\compose.yml" config --quiet
if errorlevel 1 (
    echo [FAIL] Compose configuration validation failed.
    goto finish
)
call docker image inspect ppt-agent-backend:dev >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Missing ppt-agent-backend:dev. Build the backend image first.
    goto finish
)
call docker image inspect ppt-agent-frontend:dev >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Missing ppt-agent-frontend:dev. Build the frontend image first.
    goto finish
)

echo [1/4] Starting PostgreSQL and API; waiting for health checks...
call docker compose --env-file "deploy\.env" -f "deploy\compose.yml" up -d --wait --wait-timeout 90 postgres api
if errorlevel 1 (
    echo [FAIL] Database or API startup check failed.
    goto finish
)

echo.
echo [2/4] Checking database, Dify app access and writable directories...
call docker compose --env-file "deploy\.env" -f "deploy\compose.yml" run --rm --no-deps worker python /app/worker_preflight.py
if errorlevel 1 (
    echo [FAIL] Worker preflight failed. Read the failed check above.
    goto finish
)

echo.
echo [3/4] Starting all four PPT services; waiting for health checks...
call docker compose --env-file "deploy\.env" -f "deploy\compose.yml" up -d --wait --wait-timeout 90 postgres api worker frontend
if errorlevel 1 (
    echo [FAIL] Service health checks did not pass within the startup window.
    goto finish
)

echo.
echo [4/4] Checking database and Worker through the frontend entry point...
curl.exe --fail --silent --show-error --noproxy "*" --connect-timeout 3 --max-time 10 --retry 3 --retry-delay 1 --retry-connrefused --retry-max-time 25 "http://127.0.0.1:18080/api/health/db" >nul
if errorlevel 1 (
    echo [FAIL] Database check through frontend proxy failed.
    goto finish
)
curl.exe --fail --silent --show-error --noproxy "*" --connect-timeout 3 --max-time 10 --retry 3 --retry-delay 1 --retry-connrefused --retry-max-time 25 "http://127.0.0.1:18080/api/health/worker" >nul
if errorlevel 1 (
    echo [FAIL] Worker heartbeat check through frontend proxy failed.
    goto finish
)

set "PPT_START_RESULT=0"
echo.
echo [PASS] Four PPT services and startup checks passed.
echo [INFO] Dify app access was checked. Model inference needs a real task check.
echo [OPEN] http://127.0.0.1:18080/

:finish
echo.
if "%PPT_START_RESULT%"=="0" goto show_status
echo Startup checks stopped. Existing containers are kept for diagnosis.
echo From the project directory, inspect logs with:
echo docker compose --env-file deploy\.env -f deploy\compose.yml logs --tail 80 api worker frontend

:show_status
popd
echo.
pause
exit /b %PPT_START_RESULT%
