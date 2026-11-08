@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
call "%~dp0start.bat" --prepare-only
if errorlevel 1 exit /b 1
pushd "%~dp0"
if errorlevel 1 exit /b 1
if not exist ".venv\.build-ready-6.22.3-9.2.0" goto install_build_tools
".venv\Scripts\python.exe" -c "import PyInstaller,pytest; assert PyInstaller.__version__ == '6.22.3'; assert pytest.__version__ == '9.2.0'" >nul 2>nul
if not errorlevel 1 goto build

:install_build_tools
echo 正在安装固定版本的构建和测试依赖...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "requirements-dev.txt"
if errorlevel 1 goto failure
>".venv\.build-ready-6.22.3-9.2.0" echo PyInstaller=6.22.3 pytest=9.2.0

:build
".venv\Scripts\python.exe" "scripts\build.py" %*
if errorlevel 1 goto failure
echo.
echo 构建完成。默认输出：dist\SuishouReply.exe
popd
pause
exit /b 0

:failure
echo.
echo 构建失败。请查看上方错误，修复后重试。
popd
pause
exit /b 1
