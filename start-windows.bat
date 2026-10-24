@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title 隧道交通数字孪生系统 - 一键启动
set "PKG_VER=1.1.0"
set "RUNTIME_PY=%~dp0runtime\python.exe"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
set "TWIN_DATA_DIR=%~dp0data"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
echo.
echo ============================================================
echo   隧道交通数字孪生系统 - Windows 一键启动
echo ============================================================
if not exist "backend\main.py" goto missing_files
if not exist "frontend\dist\index.html" call :ensure_frontend
if not exist "frontend\dist\index.html" goto missing_frontend
call :seed_demo
if exist "%RUNTIME_PY%" goto portable_env
set "APP_PY=%VENV_PY%"
if exist "%VENV_PY%" goto check_env
call :find_python
if not defined PY_CMD goto no_python
echo 未检测到包内运行环境，首次启动需要联网安装依赖。
echo 建议预留 5 GB 磁盘空间，安装约 5 到 20 分钟。
call :choose_mirror
echo [1/3] 正在创建独立 Python 环境 .venv ...
%PY_CMD% -m venv ".venv"
if errorlevel 1 goto venv_fail
echo [2/3] 正在安装 CPU 版 PyTorch（体积较小，无需显卡）...
"%VENV_PY%" -m pip install --retries 1 --timeout 20 torch torchvision --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
if errorlevel 1 echo 提示：CPU 版 PyTorch 下载失败，将改从常规 PyPI 安装，文件较大，请耐心等待。
echo [3/3] 正在安装其余依赖 ...
"%VENV_PY%" -m pip install -r requirements.txt %PIP_ARGS%
if errorlevel 1 goto pip_fail
> ".venv\.twin-version" echo %PKG_VER%
goto prepare_models

:portable_env
set "APP_PY=%RUNTIME_PY%"
echo 已检测到便携运行环境，无需安装 Python 或联网下载依赖。
"%APP_PY%" -c "import fastapi, uvicorn, cv2, torch, ultralytics" >nul 2>nul
if errorlevel 1 goto runtime_fail
goto start_server

:check_env
"%APP_PY%" -c "import fastapi, uvicorn, cv2, torch, ultralytics" >nul 2>nul
if errorlevel 1 goto reinstall
if not exist ".venv\.twin-version" goto write_version
set "VENV_VER="
set /p VENV_VER=<".venv\.twin-version"
if "%VENV_VER%"=="%PKG_VER%" goto prepare_models
goto reinstall

:write_version
> ".venv\.twin-version" echo %PKG_VER%
goto prepare_models

:reinstall
echo 检测到运行环境需要更新，正在安装 requirements.txt 中的依赖 ...
call :choose_mirror
"%APP_PY%" -m pip install -r requirements.txt %PIP_ARGS%
if errorlevel 1 goto pip_fail
> ".venv\.twin-version" echo %PKG_VER%
goto prepare_models

:prepare_models
echo 正在校验模型权重；缺失或损坏时会自动下载...
"%APP_PY%" scripts\download_models.py
if errorlevel 1 goto model_fail
goto start_server

:ensure_frontend
echo 未找到预构建网页 frontend\dist\index.html。
where node >nul 2>nul
if errorlevel 1 exit /b 0
where npm.cmd >nul 2>nul
if errorlevel 1 exit /b 0
echo 检测到 Node.js，正在安装前端依赖并自动构建 ...
set "NPM_ARGS="
if defined TWIN_NPM_REGISTRY set "NPM_ARGS=--registry=%TWIN_NPM_REGISTRY%"
pushd "frontend"
call npm.cmd ci %NPM_ARGS%
if errorlevel 1 goto frontend_build_error
call npm.cmd run build
if errorlevel 1 goto frontend_build_error
popd
exit /b 0

:frontend_build_error
popd
echo [错误] 前端自动构建失败，请检查上方 npm 错误信息。
exit /b 1

:choose_mirror
set "PIP_ARGS="
if defined TWIN_PIP_INDEX set "PIP_ARGS=-i %TWIN_PIP_INDEX%"
if defined PIP_ARGS exit /b 0
choice /C YN /N /T 20 /D Y /M "是否使用清华 PyPI 镜像加速下载？[Y=是 / N=官方源] "
if errorlevel 2 exit /b 0
set "PIP_ARGS=-i https://pypi.tuna.tsinghua.edu.cn/simple"
exit /b 0

:find_python
where py >nul 2>nul
if not errorlevel 1 (
  for %%V in (3.12 3.11 3.10) do (
    py -%%V -c "import sys" >nul 2>nul
    if not errorlevel 1 (
      set "PY_CMD=py -%%V"
      goto :eof
    )
  )
)
for %%C in (python3 python) do (
  where %%C >nul 2>nul
  if not errorlevel 1 (
    %%C -c "import sys; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,12) else 1)" >nul 2>nul
    if not errorlevel 1 (
      set "PY_CMD=%%C"
      goto :eof
    )
  )
)
goto :eof

:seed_demo
if not exist "data\videos" mkdir "data\videos" >nul 2>nul
if not exist "data\models" mkdir "data\models" >nul 2>nul
if not exist "data\runs" mkdir "data\runs" >nul 2>nul
if not exist "data\calibrations" mkdir "data\calibrations" >nul 2>nul
if not exist "data\videos\demo.mp4" if exist "examples\tunnel-demo.mp4" copy /Y "examples\tunnel-demo.mp4" "data\videos\demo.mp4" >nul
exit /b 0

:start_server
set "PORT=%TWIN_PORT%"
if not defined PORT set "PORT=8000"
set "FIRST_PORT=%PORT%"
set /a LAST_PORT=FIRST_PORT+10
:find_port
netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul
if errorlevel 1 goto port_ok
echo 端口 %PORT% 被占用，尝试下一个端口...
set /a PORT+=1
if %PORT% gtr %LAST_PORT% goto ports_busy
goto find_port

:port_ok
echo.
echo 访问地址：http://127.0.0.1:%PORT%
if /i not "%TWIN_NO_BROWSER%"=="1" echo 浏览器将自动打开；若没有打开，请手动复制上面的地址。
echo 保持本窗口打开。按 Ctrl+C 或直接关闭窗口可停止服务。
if /i not "%TWIN_NO_BROWSER%"=="1" start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 240;$i++){try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%PORT%/api/health' -TimeoutSec 1; if($r.StatusCode -eq 200){Start-Process 'http://127.0.0.1:%PORT%'; break}}catch{}; Start-Sleep -Milliseconds 500}"
"%APP_PY%" -m uvicorn backend.main:app --host 127.0.0.1 --port %PORT%
set "SERVER_EXIT=%ERRORLEVEL%"
echo.
echo 服务已停止。可以关闭本窗口。
if /i not "%TWIN_NO_PAUSE%"=="1" pause
exit /b %SERVER_EXIT%

:missing_files
echo [错误] 文件不完整：未找到 backend\main.py，请重新解压整个压缩包。
goto fail_pause

:missing_frontend
echo [错误] 未找到预构建网页 frontend\dist\index.html，且未能自动构建。
echo 请下载 Windows 发布包：https://github.com/wy165611/tunnel-traffic-digital-twin/releases/latest
echo 推荐下载 TunnelTwin-Windows-x64-portable.zip，解压后再双击 一键启动.bat。
goto fail_pause

:no_python
echo [错误] 未找到包内 runtime\python.exe，也未找到 Python 3.10、3.11 或 3.12。
echo 推荐下载免安装便携版：https://github.com/wy165611/tunnel-traffic-digital-twin/releases/latest
echo 轻量版需安装 Python 3.12（64 位）：https://www.python.org/downloads/windows/
goto fail_pause

:runtime_fail
echo [错误] 包内 runtime 环境不完整或依赖损坏，请重新下载并完整解压便携版。
echo 下载地址：https://github.com/wy165611/tunnel-traffic-digital-twin/releases/latest
goto fail_pause

:model_fail
echo [错误] 模型下载或 SHA-256 校验失败，请检查网络后重试。
echo 轻量版首次启动需要联网；已有完整模型的源码安装可离线启动。
goto fail_pause

:venv_fail
echo [错误] 创建 .venv 失败。请确认当前目录可写，且磁盘空间充足。
goto fail_pause

:pip_fail
echo [错误] 依赖安装失败。请检查网络后重试；若清华镜像失败，可重新运行并选择 N。
echo 也可以删除 .venv 文件夹后重新双击本脚本。
goto fail_pause

:ports_busy
echo [错误] 从 %FIRST_PORT% 开始的 11 个端口都被占用。请关闭占用端口的程序。
echo 或先执行 set TWIN_PORT=8123，然后再次运行本脚本。
goto fail_pause

:fail_pause
echo.
if /i not "%TWIN_NO_PAUSE%"=="1" pause
exit /b 1
