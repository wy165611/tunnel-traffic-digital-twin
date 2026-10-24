# Windows 10/11 安装与使用说明

面向 Windows 10/11（64 位）用户，推荐 8 GB 以上内存；便携版和轻量版都不需要 Node.js，视频与分析数据仅在本机处理。

## 方式一：便携完整版（推荐）

便携版内置 Python 3.11、pip、CPU 版 PyTorch、依赖、预构建前端、模型和演示视频，解压后无需联网安装。

1. 从 [GitHub Releases 最新版](https://github.com/wy165611/tunnel-traffic-digital-twin/releases/latest) 下载 `TunnelTwin-Windows-x64-portable.zip`，文件应能与同页 `SHA256SUMS.txt` 中的摘要对应。

   可在 PowerShell 中校验，输出 `Hash` 应与清单一致：

   ```powershell
   Get-FileHash .\TunnelTwin-Windows-x64-portable.zip -Algorithm SHA256
   ```

2. 右键 zip 选择“全部解压缩”并解压到 `D:\TunnelTwin` 等可写目录，成功后应看到 `一键启动.bat`、`runtime`、`backend`、`frontend` 和 `data`。

   中文和带空格路径（如 `D:\隧道 数字孪生`）也支持，不要在 zip 预览窗口中直接运行。

3. 双击 `一键启动.bat`，黑色窗口应显示“已检测到便携运行环境”和 `访问地址：http://127.0.0.1:8000`，随后浏览器自动打开该地址。

   也可在解压目录的 PowerShell 中运行：

   ```powershell
   .\一键启动.bat
   ```

4. 在页面“视频管理”中上传或导入本地视频，成功后视频区域应显示画面；也可以直接使用内置演示视频。

5. 点击“开始分析”，页面应显示车辆框、轨迹、过线流量和统计图表，“数据导出”可下载 CSV 与分析报告。

6. 双击 `停止.bat`、在黑色窗口按 `Ctrl+C` 或关闭该窗口即可停止服务，终端停止后页面不再更新。

若 8000 被占用，脚本会自动尝试后续端口并打开实际地址，请以窗口显示为准。

## 方式二：轻量在线版

轻量版 `TunnelTwin-Windows-x64-lite.zip` 同样包含预构建前端、模型和演示视频，只是不包含 `runtime`  Python 环境，因此首次启动需要联网。

1. 安装 64 位 Python 3.10、3.11 或 3.12（推荐 3.12）并勾选 “Add python.exe to PATH”，在新 PowerShell 中执行 `python --version` 应显示对应版本。
2. 从 Releases 下载并完整解压 `TunnelTwin-Windows-x64-lite.zip`，成功后目录中应有 `一键启动.bat`，但没有便携版的 `runtime`。
3. 双击 `一键启动.bat`，看到 `[1/3]`、`[2/3]`、`[3/3]` 并保持窗口打开，依赖安装完成后应自动打开 <http://127.0.0.1:8000>。
4. 后续启动会直接复用 `.venv`，无需重复安装，视频导入、分析和停止方法与便携版相同。

首次安装通常需要 5–20 分钟并建议预留 5 GB 空间；需要指定镜像时，在启动前执行：

```powershell
$env:TWIN_PIP_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"
.\一键启动.bat
```

## 方式三：源码部署

源码适合需要修改代码的用户；GitHub “Download ZIP” 不含前端构建、依赖和模型，必须执行安装脚本。

先决条件：Git（可选）、64 位 Python 3.11/3.12、Node.js 20.19+ 或 22.12+（含 npm），以下命令应在 PowerShell 中执行。

1. 克隆仓库并进入目录，成功后 `Get-Location` 应位于项目根目录：

   ```powershell
   git clone https://github.com/wy165611/tunnel-traffic-digital-twin.git
   cd tunnel-traffic-digital-twin
   ```

   也可在仓库页面选择 “Download ZIP”，解压后进入包含 `scripts` 和 `start-windows.bat` 的根目录。

2. 检查版本，`python --version` 应显示 3.11/3.12，`node --version` 应显示受支持版本：

   ```powershell
   python --version
   node --version
   npm --version
   ```

3. 执行安装脚本，看到模型 `Downloaded and verified` 或 `Verified` 以及前端 `✓ built` 即成功：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
   ```

4. 启动应用，看到 `Uvicorn running` 后打开 <http://127.0.0.1:8000>：

   ```powershell
   .\start-windows.bat
   ```

源码安装也支持 `$env:TWIN_PIP_INDEX` 和 `$env:TWIN_NPM_REGISTRY = "https://registry.npmmirror.com"`；不要在 Windows 上使用仅适用于 macOS arm64 / Python 3.13 的 `requirements-locked-macos-py313.txt`。

## 数据与许可

- 发布包的视频、模型、道路配置、日志和分析结果位于解压目录的 `data/`；Windows 源码安装同样使用该目录。
- 示例视频许可见 `examples\tunnel-demo-LICENSE.md`。
- YOLO 权重及 Ultralytics 实现遵循 AGPL-3.0，VisDrone 权重另有数据集非商业研究条件，分发或商业使用前请查看 `models.json`。

## 常见问题

| 问题 | 处理方法 |
| --- | --- |
| SmartScreen 提示 | 核对文件来自本项目 Releases 且 SHA-256 一致，阅读“更多信息”后自行决定是否运行，不要使用来源不明的镜像。 |
| 杀毒软件拦截 | Python、PyTorch 或批处理可能触发误报；核对来源和摘要，必要时仅信任完整软件目录，不要关闭系统防护。 |
| 8000 端口被占用 | 等待脚本自动换端口并查看实际地址，或先执行 `$env:TWIN_PORT = "8123"` 再启动。 |
| 中文路径或空格 | 发布冒烟已覆盖此类路径；仍有问题时完整解压到 `D:\TunnelTwin`，不要在 zip 预览或受保护的 `Program Files` 中运行。 |
| 首次启动很慢 | 轻量版首次需下载依赖，所有版本首次加载模型也需要等待；保持窗口开启并查看输出，成功后会出现访问地址。 |
| 浏览器没有打开 | 手动输入窗口中的 `http://127.0.0.1:端口`，不要用 `file://` 打开 HTML。 |
| 缺少 `frontend\dist` | 使用 Releases 发布包；源码安装 Node.js 后重试启动脚本会自动构建，或重新执行 `scripts\setup-windows.ps1`。 |

更多目录与分发细节见 [Windows 分发版启动说明](Windows分发版启动说明.md)。
