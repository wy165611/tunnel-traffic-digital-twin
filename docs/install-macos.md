# macOS 安装与使用说明

适用于 Apple Silicon（arm64）和 Intel（x86_64）Mac；以下命令在“终端”中执行，项目默认只监听本机 `127.0.0.1`。

## 一、安装先决条件

需要 Xcode Command Line Tools、Homebrew、Python 3.11–3.13、Node.js 20.19+ 或 22.12+（含 npm）。

1. 安装 Xcode Command Line Tools，系统应出现安装窗口；若已安装会提示 `command line tools are already installed`：

   ```bash
   xcode-select --install
   ```

2. 按 [Homebrew 官网](https://brew.sh/) 的官方说明安装 Homebrew，执行 `brew --version` 应显示版本号：

   ```bash
   brew --version
   ```

3. 安装 Python 3.13 和 Node.js，成功后 `python3 --version` 应为 3.11–3.13，`node --version` 应满足上述版本要求：

   ```bash
   brew install python@3.13 node
   python3 --version
   node --version
   npm --version
   ```

   已安装受支持版本时无需重复安装；若命令未找到，请先按 Homebrew 输出配置 shell 的 PATH，再打开新终端。

## 二、下载并安装项目

1. 克隆仓库并进入项目根目录，成功后 `pwd` 应以 `/tunnel-traffic-digital-twin` 结尾：

   ```bash
   git clone https://github.com/wy165611/tunnel-traffic-digital-twin.git
   cd tunnel-traffic-digital-twin
   ```

   也可下载源码 ZIP，解压后在终端进入包含 `scripts/setup.sh` 和 `start.sh` 的目录。

2. 执行安装脚本，看到模型 `Downloaded and verified` 或 `Verified` 以及前端 `✓ built` 即安装完成：

   ```bash
   bash scripts/setup.sh
   ```

   脚本会创建 `.venv`、安装 Python 依赖、下载并按 SHA-256 校验模型、准备演示视频、执行 `npm ci` 并构建前端；首次下载较大，请保持网络连接。

3. 启动服务，终端应显示 `隧道交通数字孪生：http://127.0.0.1:8000` 和 `Uvicorn running`：

   ```bash
   ./start.sh
   ```

4. 在浏览器打开 <http://127.0.0.1:8000>，应能看到系统页面和内置演示视频。

5. 在“视频管理”中上传或导入 MP4/MOV/AVI/MKV/WebM，视频区域出现画面后点击“开始分析”，页面应显示车辆框、轨迹、过线流量和统计结果。

6. 在“数据导出”查看报告和 CSV，结果保存在 `backend/data/runs`；回到启动终端按 `Ctrl+C`，终端返回 shell 提示符即服务已停止。

若 ZIP 解压后脚本没有执行权限，在项目根目录执行以下命令后再启动：

```bash
chmod +x start.sh scripts/setup.sh scripts/dev.sh
```

## 三、Apple Silicon 与 Intel 运行方式

- **Apple Silicon：** 默认 `detector.device: auto` 使用 CPU；如需尝试 MPS 加速，将 `config.yaml` 中的 `detector.device` 改为 `mps` 后重启，模型加载后的设备信息应显示 `mps`。
- **Intel：** 使用 CPU，保持 `detector.device: auto` 或设为 `cpu` 即可，不需要 NVIDIA 显卡。
- MPS 是否更快取决于模型、视频分辨率和 macOS/PyTorch 版本；遇到算子不支持时改回 `cpu`。

```yaml
detector:
  device: mps  # Apple Silicon 可选；Intel 或兼容性问题请改为 cpu
```

## 四、依赖锁定与下载镜像

`requirements-locked-macos-py313.txt` 是 **macOS arm64 + Python 3.13** 已验证依赖版本的锁定清单；`bash scripts/setup.sh` 仅在该环境自动使用它，其他 macOS 环境使用 `requirements.txt` 的兼容范围。

需要显式选择兼容配置时执行：

```bash
TWIN_DEPENDENCY_PROFILE=compatible bash scripts/setup.sh
```

Python 或 npm 官方源较慢时，可在安装命令前设置可选镜像；成功后仍应看到模型校验和前端构建输出：

```bash
TWIN_PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
TWIN_NPM_REGISTRY=https://registry.npmmirror.com \
bash scripts/setup.sh
```

这些镜像只加速 Python/npm 依赖，模型仍从 `models.json` 记录的官方来源下载并校验 SHA-256。

## 五、常见问题

| 问题 | 处理方法 |
| --- | --- |
| Gatekeeper 提示“无法验证开发者” | 确认源码来自本项目 GitHub；在“系统设置 → 隐私与安全性”查看被拦截项目并自行决定是否允许，不要从不明来源下载或关闭 Gatekeeper。 |
| 终端没有权限访问文件夹 | 在“系统设置 → 隐私与安全性 → 文件与文件夹”允许终端访问所需位置，必要时授予“完全磁盘访问”；也可把项目移到当前用户有权限的主目录，不要使用 `sudo` 启动。 |
| OpenCV 无法读取视频或摄像头 | 在“隐私与安全性 → 摄像头”允许终端访问摄像头，并检查“文件与文件夹”权限；确认视频路径可读且文件未损坏，普通本地视频不需要摄像头权限。 |
| 8000 端口被占用 | 执行 `TWIN_PORT=8001 ./start.sh`，终端应显示并成功访问 `http://127.0.0.1:8001`。 |
| 首次下载模型很慢 | 保持终端和网络开启，成功时会显示 `Downloaded and verified`；依赖可用上方镜像，模型会按 `models.json` 重试并校验，不要替换为来源不明的权重。 |
| `bad interpreter` 或脚本权限错误 | 确保仓库使用 LF 的 `.sh` 文件（项目已通过 `.gitattributes` 固定），再执行 `chmod +x start.sh scripts/setup.sh scripts/dev.sh`。 |
| 前端未构建 | 在项目根目录重新执行 `bash scripts/setup.sh`，或进入 `frontend` 执行 `npm ci && npm run build`，成功后应存在 `frontend/dist/index.html`。 |

## 六、开发模式（可选）

需要前后端热更新时，先完成安装，再在项目根目录执行 `bash scripts/dev.sh`；后端健康检查通过后 Vite 会显示前端开发地址，按 `Ctrl+C` 停止。仅日常使用不需要此命令。
