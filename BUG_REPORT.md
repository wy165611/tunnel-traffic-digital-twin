# 缺陷审计报告

审计日期：2026-10-13。范围是仓库根目录的后端、前端、脚本、`config.yaml` 与 `models.json`。本次只记录缺陷，没有修改应用代码。`交付/` 下的源码包是副本，未单独再审一遍。

## 测试结果

环境是 Linux、Python 3.12.3、Node.js 22.14.0。`requirements-locked-macos-py313.txt` 只适用于 macOS arm64 / Python 3.13，本次没有使用。为了能在本机跑测试，从 PyTorch CPU 索引安装了与 `requirements-verified.txt` 相同的 `torch==2.11.0+cpu`、`torchvision==0.26.0+cpu`，其余依赖按 `requirements.txt` 的范围安装。没有下载模型权重，也没有演示视频。

| 检查 | 结果 |
| --- | --- |
| `pytest -q` | **88 passed**，1 条警告（Starlette 提示 `httpx` TestClient 已弃用） |
| `npm --prefix frontend test` | **31 passed**，0 failed |
| `scripts/check_runtime.py` | 通过：本机 HTTP、带可信 Origin 的空闲 WebSocket、SIGINT 后正常退出、数据目录隔离 |
| `uvicorn` 冒烟 | `GET /api/health` 返回 200，`model_loaded` 为 false（尚未分析，符合预期） |
| 前端页面 | 仓库没有 `frontend/dist`，直接访问后端根路径返回 404。开发页测试已通过，未再做浏览器点击验收 |
| `scripts/smoke_video.py` | 未运行。仓库不含演示视频和权重，无法做真实检测冒烟 |

现有测试没有覆盖下面已确认的问题，所以全绿不能说明这些路径是对的。

## 已确认缺陷

### 1. Linux 安装会拉上 CUDA 13，而不是文档里的 CPU 版 PyTorch

- 严重程度：高
- 位置：`scripts/setup.sh` 第 14–16 行；`requirements.txt` 第 7–8 行
- 现象：在 Linux 上 `./scripts/setup.sh` 会走 `compatible`，执行 `pip install -r requirements.txt`。当前 PyPI 上满足 `torch>=2.6,<3` 的最新版是 2.14.1，它在 Linux 上硬依赖 `cuda-toolkit==13.0.3`、`nvidia-cudnn-cu13`、`nvidia-nccl-cu13`、`nvidia-cusparselt-cu13`、`nvidia-nvshmem-cu13` 等。CPU 机器也会下载一整套 CUDA 包，和 README「CPU 无需 NVIDIA 驱动」以及 Windows 安装脚本使用的 CPU 索引不一致。磁盘不足或这些包解析失败时，安装会在 `set -e` 处直接停住。
- 确认方式：新建空虚拟环境后执行 `pip install -r requirements.txt --dry-run`，解析结果包含 `torch-2.14.1` 和上述 CUDA / NVIDIA 包。对照命令 `pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --dry-run` 解析到的是 `torch-2.14.1+cpu`。Windows 脚本先装 CPU 索引，随后的 `pip install -r requirements.txt` 没有 `--upgrade`，已满足范围的 `+cpu` 包不会被换掉；Linux 脚本没有这一步。
- 建议修复：`setup.sh` 与直接使用 `requirements.txt` 的说明都改为先从 CPU 索引安装匹配的 `torch` / `torchvision`，或把 Linux CPU 轮子写进单独的约束文件。不要用无索引限制的 `torch>=2.6,<3` 作为 Linux 的唯一安装入口。

### 2. 标定声称必须按左上→右上→右下→左下，实际只检查凸性，点序反了会把速度放大数倍

- 严重程度：高
- 位置：`backend/calibration/homography.py` 第 16–19 行；同样的几何会经 `backend/api/schemas.py` 的 `SceneInput` 进入这里
- 现象：错误文案写的是四点必须按左上、右上、右下、左下。代码只调用 `cv2.isContourConvex` 和面积阈值。顺时针和逆时针的凸四边形都会通过。矩形中心仍会映射到标定矩形中心，孪生图看起来像对准了，但宽和长被换到了另一条边上。用 200×500 像素、10 m × 50 m 的矩形试过：正确顺序下水平 20 像素、1 秒是 3.6 km/h；改成左上→左下→右下→右上后，同一位移变成约 18 km/h，正好是 5 倍。从别的角开始的旋转顺序也会被接受。
- 确认方式：直接构造 `RoadCalibration`。交叉四边形和共线点会被拒绝（现有测试覆盖了这些），反向绕序不会。现有 `test_homography_corners_and_midpoint` 只验证了正确顺序。
- 建议修复：在凸性之外检查绕序和第一条边的方向，例如连续边的叉积符号必须与目标矩形一致，且第一条边对应宽度方向。不符合时沿用现在的错误提示并拒绝保存。补上反向绕序和错起点的回归，断言速度量级而不是只看中心点。

### 3. 视频实际结束后，若容器报告的帧数偏大，再点播放不会从头重开

- 严重程度：中
- 位置：`backend/service.py` 第 150–153 行
- 现象：播放到解码结束时，处理器留在原地，状态变成 `ended`。再次播放只有在 `reader.index >= reader.frames` 时才从 0 重建统计段。`frames` 来自 `CAP_PROP_FRAME_COUNT`。当这个数大于真正解出来的帧数时，结束后 `index` 仍小于 `frames`，播放请求把状态设回 `playing`，下一帧 `read()` 立刻返回空，分析马上再次结束，统计段也不会重建。界面上的「开始分析」像是没有反应。
- 确认方式：用 25 帧的 libx264 文件跑到 `ended`（此时 index 为 25），再把 `reader.frames` 改成 75，调用播放。状态变为 `playing`，下一次 `step()` 返回 `None`，run id 不变。本次用 mp4v、libx264、mpeg4 和一段短 VFR 生成的文件，OpenCV 报告的帧数和实际解码帧数一致，所以这些文件不会触发；触发条件就是代码自己依赖的那个可能偏大的帧数。
- 建议修复：结束后用 `status == 'ended'` 或「上一次读取已经到 EOF」来决定重开，不要只用容器帧数。`restart` 可以继续强制从 0 开始。

### 4. 人工速度评测把多条真值配到同一次测量上

- 严重程度：中
- 位置：`backend/evaluation.py` 第 67–75 行（schema 1，`scripts/evaluate.py` 走这里）
- 现象：同一车辆、容差内的每条速度真值都会取「时间最近的那一个机器样本」，没有一对一占用。两条真值可以都配上同一次 36 km/h 测量。覆盖率会被抬到 100%，MAE 是这几条误差的平均，不能代表独立样本。事件对照使用了 Hungarian 一对一，速度对照没有。界面用的 schema 2 明确不评速度，所以这个问题出现在 schema 1 / CLI，不会出现在当前人工评测弹窗的速度栏。
- 确认方式：临时统计段里只有一行 `timestamp=1.00, vehicle_id=1, speed=36, observed=true`。真值两条分别为 1.00 秒 10 km/h 和 1.05 秒 50 km/h，容差 0.15 秒。`evaluate_run` 返回 `matched_samples=2`、`coverage=1.0`、`mae_kmh=20.0`。
- 建议修复：按车辆分组后做一对一匹配，一条机器样本最多对应一条真值；配不上的真值计入未覆盖，不要重复使用同一次测量。

### 5. 车辆离开画面或被滤掉之后，再次出现会用直线补出一次过线

- 严重程度：中
- 位置：`backend/processor.py` 第 68–73 行与第 111–112 行；`backend/traffic/flow_counter.py` 第 16–29 行
- 现象：接触点超出原视频范围，或跟踪丢失帧数超过 `min(max_age, detection_interval*2)` 时，这一帧直接 `continue`，不会更新该 ID 的上一个过线点。计数器仍保留上一次在画面内的点。车辆从线的一侧消失、再从另一侧进入时，两点连线会与计数线相交并记一次。同一 ID 只计一次，所以这次假过线还会挡住之后的真过线。正常的隔帧检测不是这个问题：相邻两次实际观测之间的线段是设计行为。
- 确认方式：`FlowCounter([[100,0],[100,200]])` 先更新 `(10, 50)` 不计，再更新 `(180, 50)` 返回 True，`crossing_count` 变为 1。处理器在越界和丢失分支都不会调用 `flow.update`，因此会把这种跳跃交给计数器。
- 建议修复：目标被跳过或观测间隔明显大于检测周期时，丢掉该 ID 的 `previous`，下一次出现只作为新线段的起点，不补计中间未知路径。给「出画再从另一侧进入」加回归。

### 6. 依赖检查命令不读取锁文件

- 严重程度：低
- 位置：`scripts/lock_dependencies.py` 第 34–38 行；由 `scripts/setup.sh` 第 20 行调用
- 现象：`--check` 会遍历当前环境是否满足 `requirements.txt` 的范围，然后打印 `Project dependency constraints: PASS`。它不打开 `requirements-locked-macos-py313.txt`。锁文件被改乱、少行或版本与本机不一致，只要仍落在范围里，检查也会通过。
- 确认方式：阅读该分支。`--check` 在算出闭包后没有和锁文件比较。
- 建议修复：在锁定平台上把闭包与锁文件逐行比较；其他平台明确打印「未对照锁文件」，不要使用同一种 PASS 文案。

### 7. 超过 60 分钟的时间显示没有小时位

- 严重程度：低
- 位置：`frontend/src/api.ts` 第 8 行
- 现象：`formatTime` 把 `floor(秒/60)` 直接当作分，秒只取余数。90 秒会显示 `01:30.0`，但 3600 秒会显示 `60:00.0`，而不是 `01:00:00.0`。进度条、统计段起点和报告里的时间都用这个函数。
- 确认方式：函数本身没有小时分量。短演示视频看不出来，长录像的界面时间会错位。
- 建议修复：先取小时，再对 60 取分和秒；不足一小时时可以继续只显示分和秒。

### 8. 开发启动脚本不会发现后端没起来

- 严重程度：低
- 位置：`scripts/dev.sh` 第 4–8 行
- 现象：脚本开了 `set -e`，但 uvicorn 放在后台。虚拟环境不存在、端口被占用或进程马上退出时，脚本仍会进入 `npm run dev`。前端起来后 API 和 WebSocket 失败，退出时的 trap 也杀不到已经消失的后端。
- 确认方式：阅读控制流。后台命令的失败不会让当前 shell 因 `set -e` 退出。
- 建议修复：启动后轮询 `/api/health`，失败则打印日志并退出；或前台分别启动两个进程。

## 疑似缺陷

这些能从代码看出不一致，但本次没有用真实长视频或损坏文件走到界面崩溃，所以不列入上面的已确认项。

### S1. 预测帧仍带着上一次速度进入逐帧平均

- 严重程度：低
- 位置：`backend/processor.py` 第 96–99 行、第 122–126 行；`backend/traffic/traffic_metrics.py` 第 6 行、第 14–15 行
- 现象：非观测帧只要预测点还在标定多边形里，就把上一笔速度写进车辆和 `traffic_statistics` 的平均 / 最大 / 最小速度。速度估计器本身没有把预测点当成新样本，报告里的速度样本也要求 `observed=true`。直接对车辆 CSV 的 `speed` 列取平均，或看仪表上的逐帧均速，会把保持不变的旧速度再算进去。检测间隔为 2 时，大约一半的统计行是这种保持值。
- 确认方式：阅读赋值顺序。`observed == false` 时不调用 `estimator.update`，但 `world is not None` 时仍复制 `state.speed`。
- 建议修复：预测帧的速度和加速度留空，或在汇总时只纳入 `observed` 为真的车辆；CSV 与仪表使用同一口径。

### S2. 车道趋势里覆盖秒数为空时，报告弹窗会在渲染时抛错

- 严重程度：低
- 位置：`backend/reports.py` 第 156 行附近把单元格交给 `number()`；`frontend/src/components/LaneTrends.tsx` 第 13 行调用 `covered_seconds.toFixed`
- 现象：空单元格经 `number()` 变成 `null`。历史报告仍会返回这一行。前端对 `null` 调用 `toFixed` 会抛 TypeError，整份报告弹窗无法继续渲染。正常分析写出的整数不会触发。
- 确认方式：`number('')` 返回 `None`；组件没有空值判断。没有拿损坏 CSV 打开页面。
- 建议修复：前端在格式化前判断空值；后端丢弃或标出无法解析的车道行。

## 本次核对后未当作缺陷的部分

- 未标定时速度、世界坐标和速度类报警保持为空；现有回归仍阻止用默认米数生成车速。
- 过线的有限线段求交与「同一 ID 只计一次」在现有测试和公式核对中一致。正确点序下，窗口速度的 m/s 到 km/h（×3.6）与单测一致。
- WebSocket 与浏览器写操作有 Origin / Host 限制；上传在接收体阶段有 2 GB 上限。
- 前端画布按 `display/original` 缩放检测框；解码快照与车辆框成对提交。指标卡仍读最新状态，可能比画面早一帧，幅度小，未单列为缺陷。
- `scripts/check_runtime.py` 在本机可以完成启动和退出。Windows 的 `start-windows.bat` 与 CPU 索引安装步骤没有在 Windows 上执行。
