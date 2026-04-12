@echo off
set "PATH=E:\Code\okxQuantitative\tmp\reset-fixture-config\stubs;%PATH%"
set "APPDATA=E:\Code\okxQuantitative\tmp\reset-fixture-config\appdata"
call reset.bat /force /config > run_config.txt 2>&1
exit /b %errorlevel%
