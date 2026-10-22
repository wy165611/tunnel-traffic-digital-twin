@echo off
chcp 65001 >nul
setlocal EnableExtensions
echo 正在查找由本系统启动的后端进程...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=@(Get-CimInstance Win32_Process | Where-Object {$_.CommandLine -match 'backend\.main:app' -and $_.Name -match 'python'}); if($p.Count -eq 0){Write-Host '未发现正在运行的后端。'; exit 2}; $p | ForEach-Object {Write-Host ('PID=' + $_.ProcessId + '  ' + $_.Name)}; exit 0"
if errorlevel 2 goto not_running
if errorlevel 1 goto failed
choice /C YN /N /T 30 /D N /M "确定停止以上后端进程？[Y/N] "
if errorlevel 2 goto cancelled
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object {$_.CommandLine -match 'backend\.main:app' -and $_.Name -match 'python'} | ForEach-Object {Stop-Process -Id $_.ProcessId -Force}; Write-Host '后端已停止。'"
pause
exit /b 0

:not_running
echo 后端没有在运行。若浏览器仍显示旧页面，请刷新或关闭浏览器。
pause
exit /b 0

:failed
echo 查找进程失败。请关闭正在运行的一键启动窗口，或按 Ctrl+C 停止。
pause
exit /b 1

:cancelled
echo 已取消，未停止任何进程。
pause
exit /b 0
