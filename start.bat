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

:: Sync backend
echo [1/2] Syncing backend...
cd /d "%BACKEND_DIR%"
uv sync >nul 2>&1

:: Check frontend
echo [2/2] Checking frontend...
cd /d "%FRONTEND_DIR%"
if not exist "node_modules\electron" (
    echo      Installing npm packages...
    call npm install
)

echo.

:: 1. Start backend (in new window with logs visible)
echo [START] Backend API...
start "OKX Backend" cmd /k "cd /d %BACKEND_DIR% && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

:: Wait for backend to be ready
echo [WAIT] Waiting for Backend (localhost:8000)...
:wait_backend
curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 1 /nobreak >nul
    goto :wait_backend
)
echo [OK] Backend ready

:: 2. Start Vite dev server (background)
echo [START] Vite dev server...
cd /d "%FRONTEND_DIR%"
start /b npx vite --port 5173 >nul 2>&1

:: 3. Wait for Vite to be ready
echo [WAIT] Waiting for Vite (localhost:5173)...
:wait_vite
curl -s http://localhost:5173 >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 1 /nobreak >nul
    goto :wait_vite
)
echo [OK] Vite ready

:: 4. Start Electron
echo [START] Electron...
cd /d "%FRONTEND_DIR%"
npx electron .
