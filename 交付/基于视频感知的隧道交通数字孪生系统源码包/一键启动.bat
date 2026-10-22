@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "start-windows.bat" (
  echo 未找到 start-windows.bat，请重新解压完整压缩包。
  pause
  exit /b 1
)
call "%~dp0start-windows.bat"
