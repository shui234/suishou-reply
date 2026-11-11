@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall-native-host.ps1" -InstallRoot "%~dp0."
set "uninstallResult=%ERRORLEVEL%"
echo.
pause
exit /b %uninstallResult%
