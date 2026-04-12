@echo off
set "PATH=E:\Code\okxQuantitative\tmp\reset-fixture-default\stubs;%PATH%"
set "APPDATA=E:\Code\okxQuantitative\tmp\reset-fixture-default\appdata"
call reset.bat /force > run_default.txt 2>&1
exit /b %errorlevel%
