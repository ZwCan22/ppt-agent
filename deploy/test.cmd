@echo off
setlocal EnableExtensions DisableDelayedExpansion
title PPT Agent Backend Tests
pushd "%~dp0..\backend"
if errorlevel 1 (
    echo [FAIL] Cannot open the backend directory.
    pause
    exit /b 1
)
if not exist "..\.venv\Scripts\python.exe" (
    echo [FAIL] Project Python environment was not found.
    popd
    pause
    exit /b 1
)
echo PPT Agent - backend regression tests
echo.
"..\.venv\Scripts\python.exe" -B -m unittest discover -s tests -t . -v
set "PPT_TEST_RESULT=%ERRORLEVEL%"
echo.
if "%PPT_TEST_RESULT%"=="0" (
    echo [PASS] Backend tests passed.
) else (
    echo [FAIL] Backend tests failed. Read the failure above.
)
popd
echo.
pause
exit /b %PPT_TEST_RESULT%
