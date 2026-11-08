@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
pushd "%~dp0"
if errorlevel 1 goto directory_error

if not exist "main.py" goto missing_files
if exist ".venv\Scripts\python.exe" goto check_environment

echo 首次运行：正在寻找 64 位 Python 3.11 至 3.15...
for %%V in (3 3.15 3.14 3.13 3.12 3.11) do (
    py -%%V -c "import struct,sys; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,16) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "BOOTSTRAP=py -%%V"
        goto create_environment
    )
)
python -c "import struct,sys; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,16) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
if errorlevel 1 goto missing_python
set "BOOTSTRAP=python"

:create_environment
echo 正在创建本目录的 .venv 环境...
%BOOTSTRAP% -m venv ".venv"
if errorlevel 1 goto environment_error

:check_environment
".venv\Scripts\python.exe" -c "import struct,sys; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,16) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
if errorlevel 1 goto invalid_environment
if not exist ".venv\.runtime-ready-6.12.0" goto install_dependencies
".venv\Scripts\python.exe" -c "import PySide6,shiboken6; assert PySide6.__version__ == '6.12.0'; assert shiboken6.__version__ == '6.12.0'; from PySide6 import QtCore,QtGui,QtWidgets,QtNetwork" >nul 2>nul
if not errorlevel 1 goto launch

:install_dependencies
echo 首次运行：安装固定版本的运行依赖，需要联网，请稍候...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "requirements.txt"
if errorlevel 1 goto install_error
".venv\Scripts\python.exe" -c "from PySide6 import QtCore,QtGui,QtWidgets,QtNetwork; import shiboken6" >nul 2>nul
if errorlevel 1 goto install_error
>".venv\.runtime-ready-6.12.0" echo PySide6-Essentials=6.12.0

:launch
if /i "%~1"=="--prepare-only" (
    popd
    exit /b 0
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py" %*
if errorlevel 1 goto launch_error
popd
exit /b 0

:missing_python
echo 未找到受支持的 Python。请安装 Windows 64 位 Python 3.11 至 3.15，再双击本文件。
echo 官方下载：https://www.python.org/downloads/windows/
echo 如果已有 dist\SuishouReply.exe，可以直接运行 EXE，无需 Python。
goto failure

:invalid_environment
echo 本目录 .venv 中的 Python 不兼容或已移动。请重命名 .venv 文件夹后重试。
echo 需要 Windows 64 位 Python 3.11 至 3.15。
goto failure

:environment_error
echo 创建环境失败。请检查 Python 安装及当前文件夹的写入权限。
goto failure

:install_error
echo 安装依赖失败。请检查网络及上方错误，再双击重试；成功前不会写入安装标记。
goto failure

:missing_files
echo 缺少 main.py。请先完整解压整个项目，不要只复制此启动文件。
goto failure

:launch_error
echo 启动失败。可以在本目录运行 .venv\Scripts\python.exe main.py 查看错误。
goto failure

:directory_error
echo 无法打开程序所在目录。请将完整项目解压到可访问的文件夹。
pause
exit /b 1

:failure
popd
pause
exit /b 1
