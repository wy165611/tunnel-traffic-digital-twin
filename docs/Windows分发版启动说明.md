# 隧道交通数字孪生系统 · Windows 版启动说明

适用系统：Windows 10 / Windows 11（64 位）  
版本：1.1.0（2026-10-24）

> 面向新用户的三种部署方式、逐步命令和成功标志已整理到 [Windows 安装与使用说明](install-windows.md)；本页保留分发包目录、数据和故障处理细节。

> **最简单的用法：** 从 GitHub Releases 下载便携完整版，完整解压后双击 `一键启动.bat`。不需要安装 Python 或 Node.js，也不需要联网下载依赖。

## 一、下载与解压

1. 打开最新版发布页：<https://github.com/wy165611/tunnel-traffic-digital-twin/releases/latest>。
2. 下载 `TunnelTwin-Windows-x64-portable.zip`，不要点击 GitHub 页面的 “Download ZIP”（那是源码，不含预构建网页和模型）。
3. 右键 zip，选择 **全部解压缩**。建议解压到 `D:\TunnelTwin` 等可写目录；`D:\隧道 数字孪生` 这类中文、带空格路径也已纳入发布冒烟测试。
4. 确认目录中有 `一键启动.bat`、`start-windows.bat`、`runtime`、`backend`、`frontend`、`data` 等文件。不要放入 `C:\Program Files` 等需要管理员权限的目录。

可用 `SHA256SUMS.txt` 校验下载完整性，例如在 PowerShell 中运行 `Get-FileHash .\TunnelTwin-Windows-x64-portable.zip -Algorithm SHA256`，再对照清单。

## 二、两种发布包

| 项目 | 便携完整版 | 轻量在线版 |
| --- | --- | --- |
| 文件名 | `TunnelTwin-Windows-x64-portable.zip` | `TunnelTwin-Windows-x64-lite.zip` |
| Python、pip 和全部依赖 | 已内置在 `runtime\` | 不包含 |
| CPU 版 PyTorch | 已内置 | 首次启动联网安装 |
| 前端 `frontend\dist` | 已内置 | 已内置 |
| 模型和演示视频 | 均已内置，模型按 `models.json` 校验 | 演示视频已内置；模型首次启动下载并按 `models.json` 校验 |
| 首次启动联网 | 不需要 | 需要 |
| 用户需安装 | 无 | 64 位 Python 3.10、3.11 或 3.12 |

轻量版沿用 `.venv` 安装流程。首次安装约需 5–20 分钟并建议预留 5 GB 空间；可交互选择清华 PyPI 镜像，也可预先设置 `TWIN_PIP_INDEX`。前端需要重新构建时，可通过 `TWIN_NPM_REGISTRY=https://registry.npmmirror.com` 选择 npmmirror。

## 三、电脑要求

- Windows 10 或 Windows 11，64 位。
- 推荐 8 GB 以上内存；CPU 即可运行，不需要独立显卡。
- 便携版解压和运行需要足够磁盘空间；轻量版首次安装还需联网。
- 无需 Node.js。只有源码启动且 `frontend\dist` 缺失时，脚本才会在检测到 Node.js 后自动执行 `npm ci` 和 `npm run build`。

## 四、启动软件

1. 双击 `一键启动.bat`。
2. 便携版会优先使用 `runtime\python.exe`，不会创建 `.venv` 或联网安装依赖；轻量版和源码使用 `.venv`。
3. 默认地址是 <http://127.0.0.1:8000>。若端口被占用，会从起始端口向后尝试最多 11 个端口，浏览器自动打开实际地址。
4. 若浏览器没有打开，手动输入黑色窗口中显示的 `http://127.0.0.1:端口`。
5. **运行期间不要关闭黑色命令窗口**。关闭窗口或按 `Ctrl+C` 即停止服务。

源码安装仍可在项目根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
```

## 五、用示例视频演示

1. 发布包已在 `data\videos\demo.mp4` 准备示例，页面会自动载入。
2. 点击页面上的 **开始分析**，第一次载入模型需要等待几秒。
3. 左侧可切换监测总览、感知与孪生、交通分析、事件记录、车辆明细和数据导出。
4. 示例没有真实道路尺寸标定，因此速度、加速度等米制数据显示“未标定”；检测、跟踪、过线流量和事件仍可演示。需要测速时，请在 **道路标定** 中输入实测距离。
5. 在 **视频管理** 中可上传或导入 MP4/MOV/AVI/MKV/WebM（单个不超过 2 GB），也可接入 RTSP/HTTP(S) 实时流。

## 六、文件和数据

所有可变数据都在解压目录的 `data/` 下，不使用系统临时目录保存用户数据：

- `data\videos`：导入的视频和默认演示视频。
- `data\models`：预训练模型权重。
- `data\runs`：分析结果 CSV、报告和事件截图。
- `data\calibrations`：道路、车道、计数线和标定配置。
- `data\logs`：发布冒烟等诊断日志（如生成）。

备份时复制整个 `data` 即可。软件只监听本机 `127.0.0.1`，局域网其他电脑默认无法访问。

## 七、常见问题

| 现象 | 处理方法 |
| --- | --- |
| 提示缺少 `frontend\dist` | 非开发者请从 Releases 重新下载发布包。源码用户可安装 Node.js 后重试自动构建，或手动执行 `npm --prefix frontend ci` 和 `npm --prefix frontend run build`。 |
| 提示便携运行环境损坏 | 重新完整解压便携版，确认 `runtime\python.exe` 和 `runtime\Lib\site-packages` 存在，不要只复制 bat 文件。 |
| 轻量版提示未找到 Python | 安装 64 位 Python 3.12 并勾选 “Add python.exe to PATH”，然后重新双击。便携版不需要安装 Python。 |
| 依赖安装很慢或失败 | 检查网络，换用官方源或清华镜像；仍失败可删除 `.venv` 后重试。便携版不执行此步骤。 |
| 端口 8000 被占用 | 脚本会自动换端口，以窗口实际地址为准；也可先执行 `set TWIN_PORT=8123` 再启动。 |
| 浏览器没有自动打开 | 手动输入窗口显示的地址，不要用 `file://` 打开 HTML。 |
| Windows SmartScreen 提示 | 确认 zip 来自本项目 GitHub Releases 且 SHA-256 一致；阅读提示后自行决定是否继续，不要从不明镜像下载。 |
| 杀毒软件报警或拦截 | Python、pip、PyTorch 或批处理可能触发误报。核对来源和摘要，必要时仅将可信的软件目录加入白名单，不要关闭系统防护。 |
| 提示模型缺失或校验失败 | 确认 `data\models` 未被删除；便携版建议重新下载。轻量版可用 `.venv\Scripts\python.exe scripts\download_models.py` 重新下载校验。 |
| 分析速度慢 | CPU 性能会影响速度；可降低视频分辨率或增大“检测间隔 / 帧”，首次载入模型请耐心等待。 |
| 双击后窗口一闪而过 | 确认已完整解压；在目录地址栏输入 `cmd`，执行 `一键启动.bat` 查看错误。 |

## 八、示例视频与第三方许可

- 示例视频来自 Wikimedia Commons 的 `The Rantatunneli of Tampere.webm`，作者 Sounds of Changes / Työväenmuseo Werstas / Mikael Maffei，许可 CC BY 3.0。本包截取 20 秒并转码，详见 `examples\tunnel-demo-LICENSE.md`。
- YOLO 权重及 Ultralytics 实现遵循 **AGPL-3.0**；VisDrone 权重另受其数据集非商业研究条件约束；Torchvision SSD 遵循 BSD-3-Clause。
- 权重来源、SHA-256 和许可见 `models.json`。本项目不训练模型，分发或商业使用前请遵守对应许可。

## 九、构建和发布（维护者）

在 Windows 构建机运行以下命令可本地生成两个 zip 和 `SHA256SUMS.txt`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_windows_release.ps1
```

GitHub Actions 会在 PR 和手动触发时构建、在中文且含空格的路径中冒烟测试并上传 artifact。维护者推送 `v1.1.0` 标签后，同一工作流会重新构建和验证，再发布 GitHub Release；验证失败不会发布。
