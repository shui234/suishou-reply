@echo off
setlocal EnableExtensions DisableDelayedExpansion
if exist "%~dp0dist\SuishouReply.exe" goto packaged
if exist "%~dp0dist\SuishouReply\SuishouReply.exe" goto packaged_directory
call "%~dp0start.bat" --demo
exit /b %errorlevel%

:packaged
start "" "%~dp0dist\SuishouReply.exe" --demo
exit /b %errorlevel%

:packaged_directory
start "" "%~dp0dist\SuishouReply\SuishouReply.exe" --demo
exit /b %errorlevel%
