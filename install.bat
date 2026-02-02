@echo off
setlocal enabledelayedexpansion

:: OKX Quantitative Trading System - Install Dependencies (using uv)

title OKX Quant - Install Dependencies

echo ================================================
echo        OKX Quantitative Trading System
echo             Install Dependencies
echo ================================================
echo.

:: Set project paths
set "PROJECT_ROOT=%~dp0"
set "BACKEND_DIR=%PROJECT_ROOT%backend"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"

:: ==================== Check Environment ====================

echo [CHECK] System environment...
echo.

:: Check uv
echo   uv:
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo     [NOT INSTALLED]
    echo.
    echo     Installing uv...
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    if %errorlevel% neq 0 (
        echo     [ERROR] Failed to install uv automatically
        echo     Please install manually: pip install uv
        set "UV_OK=0"
    ) else (
        echo     [OK] uv installed
        set "UV_OK=1"
    )
) else (
    for /f "tokens=*" %%i in ('uv --version 2^>^&1') do echo     %%i [OK]
    set "UV_OK=1"
)

:: Check Node.js
echo   Node.js:
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo     [NOT INSTALLED] Please download from https://nodejs.org
    set "NODE_OK=0"
) else (
    for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo     %%i [OK]
    set "NODE_OK=1"
)

echo.

:: Check minimum requirements
if "%UV_OK%"=="0" (
    echo [ERROR] Please install uv first
    goto :error
)
if "%NODE_OK%"=="0" (
    echo [ERROR] Please install Node.js first
    goto :error
)

:: ==================== Install Backend ====================

echo ================================================
echo         Installing Backend Dependencies
echo ================================================
echo.

cd /d "%BACKEND_DIR%"

echo [INSTALL] Syncing Python packages with uv...
uv sync

if %errorlevel% neq 0 (
    echo [ERROR] Failed to install backend dependencies
    goto :error
)

echo [OK] Backend dependencies installed
echo.

:: ==================== Install Frontend ====================

echo ================================================
echo        Installing Frontend Dependencies
echo ================================================
echo.

cd /d "%FRONTEND_DIR%"

:: Clean if requested
if exist "node_modules" (
    set /p REINSTALL="node_modules exists. Reinstall? [y/N]: "
    if /i "!REINSTALL!"=="y" (
        echo [CLEAN] Removing old node_modules...
        rmdir /s /q node_modules
    ) else (
        echo [SKIP] Keeping existing dependencies
        goto :frontend_done
    )
)

:: Install npm dependencies
echo [INSTALL] npm packages (this may take a few minutes)...
call npm install

if %errorlevel% neq 0 (
    echo [ERROR] Failed to install frontend dependencies
    echo [TIP] If network issues, try: npm config set registry https://registry.npmmirror.com
    goto :error
)

:frontend_done
echo [OK] Frontend dependencies installed
echo.

:: ==================== Complete ====================

echo ================================================
echo            Installation Complete
echo ================================================
echo.
echo   All dependencies installed successfully!
echo.
echo   Next steps:
echo     1. (Optional) Configure config/settings.yaml
echo     2. Run start.bat to start the system
echo.
echo ================================================

pause
goto :eof

:error
echo.
echo ================================================
echo            Installation Failed
echo ================================================
echo.
echo   Please check the error message above
echo.
pause
exit /b 1
