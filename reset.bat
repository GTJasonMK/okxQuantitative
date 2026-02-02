@echo off
setlocal enabledelayedexpansion

:: ================================================================
:: OKX Quantitative Trading System - Reset User Data
::
:: Usage:
::   reset.bat          - Reset all user data (with confirmation)
::   reset.bat /force   - Reset without confirmation
::   reset.bat /config  - Also reset .env config file
:: ================================================================

title OKX Quant - Reset

:: Parse arguments
set "FORCE=0"
set "RESET_CONFIG=0"
for %%a in (%*) do (
    if /i "%%a"=="/force" set "FORCE=1"
    if /i "%%a"=="/config" set "RESET_CONFIG=1"
)

:: Set project paths
set "PROJECT_ROOT=%~dp0"
set "DATA_DIR=%PROJECT_ROOT%data"
set "CONFIG_DIR=%PROJECT_ROOT%config"

echo.
echo ================================================
echo        OKX Quantitative Trading System
echo              Reset User Data
echo ================================================
echo.

:: Show what will be deleted
echo  The following data will be deleted:
echo.
echo    [Database]
if exist "%DATA_DIR%\market.db" (
    for %%A in ("%DATA_DIR%\market.db") do echo      - data\market.db (%%~zA bytes)
) else (
    echo      - data\market.db (not found)
)

echo.
echo    [User Preferences]
if exist "%CONFIG_DIR%\user_preferences.json" (
    echo      - config\user_preferences.json
) else (
    echo      - config\user_preferences.json (not found)
)

if "%RESET_CONFIG%"=="1" (
    echo.
    echo    [API Config]
    if exist "%CONFIG_DIR%\.env" (
        echo      - config\.env (API keys will be removed!)
    ) else (
        echo      - config\.env (not found)
    )
)

echo.

:: Confirmation
if "%FORCE%"=="0" (
    set /p CONFIRM="  Are you sure? [y/N]: "
    if /i not "!CONFIRM!"=="y" (
        echo.
        echo  [Cancelled] No data was deleted.
        echo.
        pause
        exit /b 0
    )
)

echo.
echo  [Resetting...]
echo.

:: Stop running services first
echo    Stopping services...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173.*LISTENING" 2^>nul') do taskkill /PID %%a /F >nul 2>&1
taskkill /IM electron.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul

:: Delete database
if exist "%DATA_DIR%\market.db" (
    del /f /q "%DATA_DIR%\market.db"
    if exist "%DATA_DIR%\market.db" (
        echo    [ERROR] Failed to delete market.db (may be in use)
    ) else (
        echo    [OK] Deleted market.db
    )
) else (
    echo    [SKIP] market.db not found
)

:: Delete user preferences
if exist "%CONFIG_DIR%\user_preferences.json" (
    del /f /q "%CONFIG_DIR%\user_preferences.json"
    echo    [OK] Deleted user_preferences.json
) else (
    echo    [SKIP] user_preferences.json not found
)

:: Delete .env if requested
if "%RESET_CONFIG%"=="1" (
    if exist "%CONFIG_DIR%\.env" (
        del /f /q "%CONFIG_DIR%\.env"
        echo    [OK] Deleted .env
    ) else (
        echo    [SKIP] .env not found
    )
)

:: Delete any other cache/temp files in data directory
if exist "%DATA_DIR%\*.log" (
    del /f /q "%DATA_DIR%\*.log"
    echo    [OK] Deleted log files
)

if exist "%DATA_DIR%\*.tmp" (
    del /f /q "%DATA_DIR%\*.tmp"
    echo    [OK] Deleted temp files
)

echo.
echo ================================================
echo              Reset Complete!
echo ================================================
echo.
echo  The project has been reset to initial state.
echo.

if "%RESET_CONFIG%"=="1" (
    echo  [!] Remember to configure config\.env with your API keys
    echo.
)

echo  Run start.bat to start the system.
echo.

pause
exit /b 0
