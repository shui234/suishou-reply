@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-native-host.ps1" -InstallRoot "%~dp0."
set "installResult=%ERRORLEVEL%"
echo.
pause
exit /b %installResult%
