@echo off
setlocal EnableExtensions EnableDelayedExpansion
:: OKX Quantitative Trading System - Reset Local Runtime State
:: Usage: reset.bat [/force] [/config]
title OKX Quant - Reset
set "FORCE=0"
set "RESET_CONFIG=0"
if not "%~1"=="" (
    for %%a in (%*) do (
        if /i "%%a"=="/force" set "FORCE=1"
        if /i "%%a"=="/config" set "RESET_CONFIG=1"
    )
)
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "FRONTEND_DIR=%PROJECT_ROOT%\frontend"
set "DATA_DIR=%PROJECT_ROOT%\data"
set "CONFIG_DIR=%PROJECT_ROOT%\config"
set "LOGS_DIR=%PROJECT_ROOT%\logs"
set "ENV_FILE=%CONFIG_DIR%\.env"
set "FRONTEND_PACKAGE_FILE=%FRONTEND_DIR%\package.json"
set "DATABASE_PATH_RAW="
set "DATABASE_PATH="
set "DATABASE_WAL="
set "DATABASE_SHM="
set "API_PORT="
set "APP_PRODUCT_NAME="
set "APP_PACKAGE_NAME="
set "USER_DATA_DIR="
set "USER_DATA_FALLBACK_DIR="
set "HAS_ERRORS=0"
call :load_env_values
call :resolve_database_path
call :load_app_names
call :resolve_user_data_dirs
echo.
echo ================================================
echo        OKX Quantitative Trading System
echo         Reset Local Runtime State
echo ================================================
echo.
echo  The following local runtime state will be removed:
echo.
echo    [Database]
call :preview_file "%DATABASE_PATH%"
call :preview_file "%DATABASE_WAL%"
call :preview_file "%DATABASE_SHM%"
echo.
echo    [Runtime Config]
call :preview_file "%CONFIG_DIR%\user_preferences.json"
call :preview_file "%CONFIG_DIR%\risk_control.json"
call :preview_file "%CONFIG_DIR%\market_alerts.json"
echo.
echo    [Trend Research Artifacts]
call :preview_glob "%DATA_DIR%\trend_research*.json"
call :preview_glob "%DATA_DIR%\trend_research*.pt"
call :preview_glob "%DATA_DIR%\*.tmp"
echo.
echo    [Logs]
call :preview_dir "%LOGS_DIR%"
echo.
echo    [Electron User Data]
call :preview_dir "%USER_DATA_DIR%"
if defined USER_DATA_FALLBACK_DIR call :preview_dir "%USER_DATA_FALLBACK_DIR%"
if "%RESET_CONFIG%"=="1" (
    echo.
    echo    [Config]
    call :preview_file "%ENV_FILE%"
)
echo.
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
echo    Stopping services...
call :kill_port "8000"
if defined API_PORT call :kill_port "%API_PORT%"
call :kill_port "5173"
call taskkill /IM electron.exe /F >nul 2>&1
call timeout /t 1 /nobreak >nul
call :delete_file "%DATABASE_PATH%"
call :delete_file "%DATABASE_WAL%"
call :delete_file "%DATABASE_SHM%"
call :delete_file "%CONFIG_DIR%\user_preferences.json"
call :delete_file "%CONFIG_DIR%\risk_control.json"
call :delete_file "%CONFIG_DIR%\market_alerts.json"
call :delete_glob "%DATA_DIR%\trend_research*.json"
call :delete_glob "%DATA_DIR%\trend_research*.pt"
call :delete_glob "%DATA_DIR%\*.tmp"
if exist "%LOGS_DIR%" (
    rmdir /s /q "%LOGS_DIR%" >nul 2>&1
    if exist "%LOGS_DIR%" (
        echo    [ERROR] Failed to clear %LOGS_DIR%
        set "HAS_ERRORS=1"
    ) else (
        mkdir "%LOGS_DIR%" >nul 2>&1
        if exist "%LOGS_DIR%" (
            echo    [OK] Cleared %LOGS_DIR%
        ) else (
            echo    [ERROR] Failed to recreate %LOGS_DIR%
            set "HAS_ERRORS=1"
        )
    )
) else (
    mkdir "%LOGS_DIR%" >nul 2>&1
    if exist "%LOGS_DIR%" (
        echo    [OK] Cleared %LOGS_DIR%
    ) else (
        echo    [ERROR] Failed to create %LOGS_DIR%
        set "HAS_ERRORS=1"
    )
)
call :delete_dir "%USER_DATA_DIR%"
if defined USER_DATA_FALLBACK_DIR call :delete_dir "%USER_DATA_FALLBACK_DIR%"
if "%RESET_CONFIG%"=="1" call :delete_file "%ENV_FILE%"
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%" >nul 2>&1
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%" >nul 2>&1
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%" >nul 2>&1
echo.
echo ================================================
if "%HAS_ERRORS%"=="0" (
    echo              Reset Complete!
) else (
    echo         Reset Completed With Errors
)
echo ================================================
echo.
if "%HAS_ERRORS%"=="0" (
    echo  The local runtime state has been cleared.
) else (
    echo  Some files or directories could not be removed.
)
echo.
if "%RESET_CONFIG%"=="1" (
    echo  [NOTE] Remember to recreate config\.env before using API features.
    echo.
)
echo  Run start.bat to start the system.
echo.
if "%FORCE%"=="0" pause
if "%HAS_ERRORS%"=="0" exit /b 0
exit /b 1
:load_env_values
call :read_env_value "DATABASE_PATH" DATABASE_PATH_RAW & call :read_env_value "API_PORT" API_PORT
goto :eof
:read_env_value
set "TARGET_KEY=%~1"
set "%~2="
if not exist "%ENV_FILE%" goto :eof
for /f "usebackq tokens=1* delims==" %%A in ("%ENV_FILE%") do (
    set "CURRENT_KEY=%%A"
    set "CURRENT_VALUE=%%B"
    set "CURRENT_KEY=!CURRENT_KEY: =!"
    if defined CURRENT_KEY (
        if /i not "!CURRENT_KEY:~0,1!"=="#" (
            if /i "!CURRENT_KEY!"=="%TARGET_KEY%" (
                set "%~2=!CURRENT_VALUE!"
            )
        )
    )
)
goto :eof
:resolve_database_path
if not defined DATABASE_PATH_RAW (
    set "DATABASE_PATH=%DATA_DIR%\market.db"
    goto :resolve_database_path_done
)
set "DATABASE_PATH_RAW=%DATABASE_PATH_RAW:"=%"
set "DATABASE_PATH_RAW=%DATABASE_PATH_RAW:/=\%"
if not defined DATABASE_PATH_RAW (
    set "DATABASE_PATH=%DATA_DIR%\market.db"
    goto :resolve_database_path_done
)
set "DB_PATH_FIRST_CHAR=%DATABASE_PATH_RAW:~0,1%"
set "DB_PATH_SECOND_CHAR=%DATABASE_PATH_RAW:~1,1%"
if "%DB_PATH_SECOND_CHAR%"==":" (
    set "DATABASE_PATH=%DATABASE_PATH_RAW%"
    goto :resolve_database_path_done
)
if "%DB_PATH_FIRST_CHAR%"=="\" (
    set "DATABASE_PATH=%DATABASE_PATH_RAW%"
    goto :resolve_database_path_done
)
set "DATABASE_PATH=%PROJECT_ROOT%\%DATABASE_PATH_RAW%"
:resolve_database_path_done
set "DATABASE_WAL=%DATABASE_PATH%-wal"
set "DATABASE_SHM=%DATABASE_PATH%-shm"
goto :eof
:load_app_names
if not exist "%FRONTEND_PACKAGE_FILE%" goto :eof
for /f "usebackq tokens=1* delims=:" %%A in ("%FRONTEND_PACKAGE_FILE%") do (
    set "JSON_KEY=%%A"
    set "JSON_VALUE=%%B"
    set "JSON_KEY=!JSON_KEY: =!"
    set "JSON_KEY=!JSON_KEY:"=!"
    if /i "!JSON_KEY!"=="productName" (
        set "JSON_VALUE=!JSON_VALUE:,=!"
        for /f "tokens=* delims= " %%V in ("!JSON_VALUE!") do set "APP_PRODUCT_NAME=%%~V"
        set "APP_PRODUCT_NAME=!APP_PRODUCT_NAME:"=!"
    )
    if /i "!JSON_KEY!"=="name" if not defined APP_PACKAGE_NAME (
        set "JSON_VALUE=!JSON_VALUE:,=!"
        for /f "tokens=* delims= " %%V in ("!JSON_VALUE!") do set "APP_PACKAGE_NAME=%%~V"
        set "APP_PACKAGE_NAME=!APP_PACKAGE_NAME:"=!"
    )
)
goto :eof
:resolve_user_data_dirs
if not defined APPDATA goto :eof
if defined APP_PRODUCT_NAME set "USER_DATA_DIR=%APPDATA%\%APP_PRODUCT_NAME%"
if defined APP_PACKAGE_NAME (
    if /i not "%APP_PACKAGE_NAME%"=="%APP_PRODUCT_NAME%" (
        set "USER_DATA_FALLBACK_DIR=%APPDATA%\%APP_PACKAGE_NAME%"
    )
)
goto :eof
:kill_port
if "%~1"=="" goto :eof
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%~1 .*LISTENING" 2^>nul') do call taskkill /PID %%a /F >nul 2>&1
goto :eof
:preview_file
if "%~1"=="" goto :eof
if exist "%~1" (
    for %%A in ("%~1") do echo      - %%~fA [%%~zA bytes]
) else (
    echo      - %~1 [not found]
)
goto :eof
:preview_glob
if "%~1"=="" goto :eof
dir /b /a-d "%~1" >nul 2>&1
if errorlevel 1 (
    echo      - %~1 [not found]
) else (
    echo      - %~1
)
goto :eof
:preview_dir
if "%~1"=="" goto :eof
if exist "%~1" (
    echo      - %~1
) else (
    echo      - %~1 [not found]
)
goto :eof
:delete_file
if "%~1"=="" goto :eof
if exist "%~1" (
    del /f /q "%~1" >nul 2>&1
    if exist "%~1" (
        echo    [ERROR] Failed to delete %~1
        set "HAS_ERRORS=1"
    ) else (
        echo    [OK] Deleted %~1
    )
) else (
    echo    [SKIP] %~1 not found
)
goto :eof
:delete_glob
if "%~1"=="" goto :eof
dir /b /a-d "%~1" >nul 2>&1
if errorlevel 1 (
    echo    [SKIP] %~1 not found
    goto :eof
)
del /f /q "%~1" >nul 2>&1
dir /b /a-d "%~1" >nul 2>&1
if errorlevel 1 (
    echo    [OK] Deleted %~1
) else (
    echo    [ERROR] Failed to delete %~1
    set "HAS_ERRORS=1"
)
goto :eof
:delete_dir
if "%~1"=="" goto :eof
if exist "%~1" (
    rmdir /s /q "%~1" >nul 2>&1
    if exist "%~1" (
        echo    [ERROR] Failed to delete %~1
        set "HAS_ERRORS=1"
    ) else (
        echo    [OK] Deleted %~1
    )
) else (
    echo    [SKIP] %~1 not found
)
goto :eof
