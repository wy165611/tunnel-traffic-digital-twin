# 隧道交通数字孪生系统 Windows 启动说明

适用系统：Windows 10 和 Windows 11，64 位。

本说明介绍如何安装依赖、启动系统并导入自己的交通视频。首次安装需要联网下载 Python 和前端依赖及预训练模型；准备完成后，系统在本机处理视频。源码包不含演示视频和模型权重。

## 运行前准备

请先安装以下软件：

- Python 3.11 或更高版本，64 位。安装时启用 Python Launcher，之后可以在 PowerShell 运行 `py -3`。
- Node.js 20.19 或更高版本，或 22.12 或更高版本。推荐安装 Node.js LTS。
- 预留数 GB 可用磁盘空间。首次安装会下载 CPU 版 PyTorch、其他依赖和模型权重。

官方安装页面：[Python for Windows](https://www.python.org/downloads/windows/) · [Node.js 下载](https://nodejs.org/en/download) · [PyTorch 本地安装说明](https://pytorch.org/get-started/locally/)

## 首次安装

1. 将源码 ZIP 解压到本机可写文件夹，例如 `C:\TunnelTrafficTwin`。不要直接在压缩包预览窗口中运行。
2. 在解压后的项目根目录打开 PowerShell。根目录应能看到 `README.md`、`scripts` 文件夹和 `start-windows.bat`。
3. 确认运行环境已安装：

   ```powershell
   py -3 --version
   node --version
   npm --version
   ```

   每条命令都应显示版本号。若 PowerShell 找不到命令，请安装对应软件并重新打开 PowerShell。

4. 在项目根目录运行 Windows 安装脚本：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
   ```

5. 等待脚本显示 `Setup complete`。脚本会创建项目专用 Python 虚拟环境，安装 Python 依赖，下载并核验模型权重，安装前端依赖并构建网页。安装脚本会安装 PyTorch 官方 CPU 版，系统可以在没有 NVIDIA 显卡的电脑上运行。首次安装期间保持网络连接。

Windows 安装使用 `requirements.txt`。不要使用 `requirements-locked-macos-py313.txt`，它只适用于 macOS arm64 与 Python 3.13。

## 启动和导入视频

1. 安装完成后，在项目根目录双击 `start-windows.bat`。保持弹出的命令窗口打开。
2. 浏览器打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。点击“视频管理”或“导入视频”，选择本地 MP4、MOV、AVI、MKV 或 WebM 视频。单个视频最大为 2 GB。
3. 视频载入后点击“开始分析”。首次载入模型时等待片刻。系统可以使用 CPU 运行。
4. 要停止服务，回到命令窗口按 `Ctrl+C`。以后再次使用时只需双击 `start-windows.bat`，不用重复安装。

## 常见问题

| 现象 | 处理方法 |
| --- | --- |
| `py` 或 Python 未找到 | 从 Python 官方页面安装 64 位 Python，并启用 Python Launcher。安装后关闭并重新打开 PowerShell。 |
| `npm` 未找到 | 安装 Node.js LTS。重新打开 PowerShell，再检查 `node --version` 和 `npm --version`。 |
| 模型下载失败 | 确认网络可访问模型下载源，然后重新运行安装命令。脚本会再次下载并校验权重；不要手动替换未校验的模型文件。 |
| 8000 端口被占用 | 在 PowerShell 输入 `$env:TWIN_PORT = "8001"`，然后运行 `.\start-windows.bat`，并访问 [http://127.0.0.1:8001](http://127.0.0.1:8001)。 |
| 画面加载较慢 | 首次启动会载入模型。CPU 分析速度取决于电脑性能；等待载入完成后再开始分析。 |

导入的视频、模型和分析结果保存在项目目录的 `backend\data` 中。默认服务只监听本机地址 `127.0.0.1`。模型来源和许可证见 `models.json`。
