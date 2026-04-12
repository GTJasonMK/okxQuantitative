@echo off
setlocal

:: OKX Quantitative Trading System - One-click Start

title OKX Quant

set "PROJECT_ROOT=%~dp0"
set "BACKEND_DIR=%PROJECT_ROOT%backend"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"

echo ================================================
echo        OKX Quantitative Trading System
echo ================================================
echo.

:: Close any previously running instances
echo [CLEANUP] Closing previous instances...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173.*LISTENING"') do taskkill /PID %%a /F >nul 2>&1
taskkill /IM electron.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul
echo [OK] Cleanup done
echo.

:: Quick checks
where uv >nul 2>&1 || (echo [ERROR] uv not found && pause && exit /b 1)
where node >nul 2>&1 || (echo [ERROR] Node.js not found && pause && exit /b 1)

:: Check backend
echo [1/2] Checking backend...
cd /d "%BACKEND_DIR%"
echo      Verifying backend runtime...
uv run python -c "import fastapi, uvicorn, annotated_doc" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Backend runtime dependencies are incomplete
    echo         FastAPI currently requires annotated-doc, but it is missing from the venv
    echo         Fix: cd backend ^&^& uv sync
    pause
    exit /b 1
)

:: Check frontend
echo [2/2] Checking frontend...
cd /d "%FRONTEND_DIR%"
if not exist "node_modules\electron" (
    echo [ERROR] Frontend dependencies are missing
    echo         Existing Windows node_modules is required for start.bat
    pause
    exit /b 1
)

echo.
echo [START] Single-window dev runtime...
cd /d "%PROJECT_ROOT%"
node tools\startDevRuntime.cjs
