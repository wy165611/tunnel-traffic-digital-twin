# 缺陷审计报告

审计日期：2026-10-13。范围是仓库根目录的后端、前端、脚本、`config.yaml` 与 `models.json`。  
**修复批次：2026-10-13**（分支 `cursor/bug-audit-report-1d52`）。下列条目均已在本分支修复，并补充回归测试（见各条「修复说明」）。

## 测试结果（修复后）

环境：Linux、Python 3.12.3、Node.js 22.14.0。测试使用 CPU 版 PyTorch（与 `requirements-verified.txt` 一致），`TWIN_DATA_DIR` 指向临时目录。

| 检查 | 结果 |
| --- | --- |
| `pytest -q` | **96 passed**，1 条 Starlette/httpx 弃用警告 |
| `npm --prefix frontend test` | **32 passed**，0 failed |
| `scripts/check_runtime.py` | 通过（HTTP、可信 Origin WebSocket、正常退出、隔离数据） |
| 无 `frontend/dist` 时 `GET /` | 返回 200 与中文构建说明（不再裸 404） |

## 已确认缺陷

### 1. Linux 安装会拉上 CUDA 13，而不是文档里的 CPU 版 PyTorch — **已修复**

- 严重程度：高
- 位置：`scripts/setup.sh`（`compatible` 分支）
- 修复说明：`compatible` 安装路径与 Windows 一致，先执行 `pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu`，再安装 `requirements.txt` 其余依赖。
- 回归：安装脚本逻辑审查；`lock_dependencies.py --check` 在非锁定平台仍校验 `requirements.txt` 范围。

### 2. 标定点序仅检查凸性，反序会导致速度量级错误 — **已修复**

- 严重程度：高
- 位置：`backend/calibration/homography.py`（`validate_corner_order`）
- 修复说明：在凸性校验后，按图像坐标推断几何上的左上/右上/右下/左下索引，要求用户点击顺序必须为 `[0,1,2,3]` 对应 TL→TR→BR→BL，否则拒绝保存。
- 回归：`tests/test_core.py` 中 `test_calibration_rejects_wrong_corner_order`、`test_calibration_horizontal_speed_scale`。

### 3. 分析结束后容器帧数偏大时，再点播放不会重开 — **已修复**

- 严重程度：中
- 位置：`backend/service.py`（`control` → `play`）
- 修复说明：记录 `resume_from_ended`；在 `ended` 后播放或索引已到末尾时重建 processor，并从时间 0 开始新统计段。
- 回归：`tests/test_api.py::test_play_after_ended_restarts_segment`。

### 4. schema 1 速度评测重复使用同一次测量 — **已修复**

- 严重程度：中
- 位置：`backend/evaluation.py`
- 修复说明：按 `vehicle_id` 分组后，对真值与机器样本做 Hungarian 一对一匹配（与事件评测一致），每条测量最多匹配一条真值。
- 回归：`tests/test_evaluation.py::test_speed_evaluation_matches_one_measurement_to_one_truth`；原有 `test_eval_errors_coverage_and_one_to_one_events` 仍通过。

### 5. 出画后再出现会用直线补记过线 — **已修复**

- 严重程度：中
- 位置：`backend/processor.py`、`backend/traffic/flow_counter.py`（`forget`）
- 修复说明：跟踪因越界或丢失帧被跳过时，清除该 ID 在 `FlowCounter` 中的 `previous`，避免跨空白线段误计。
- 回归：`tests/test_counting_line.py::test_flow_counter_does_not_bridge_off_screen_jump`。

### 6. `lock_dependencies.py --check` 不对照锁文件 — **已修复**

- 严重程度：低
- 位置：`scripts/lock_dependencies.py`
- 修复说明：在 macOS arm64 / Python 3.13 上与 `requirements-locked-macos-py313.txt` 逐包比对；其他平台打印明确说明未对照锁文件，仍校验 `requirements.txt` 闭包。
- 回归：脚本逻辑与 `setup.sh` 调用链。

### 7. 超过 60 分钟的时间显示无小时位 — **已修复**

- 严重程度：低
- 位置：`frontend/src/api.ts`（`formatTime`）
- 修复说明：不足 1 小时仍为 `MM:SS.t`；≥1 小时为 `HH:MM:SS.t`。
- 回归：`frontend/tests/api.test.mjs`。

### 8. `dev.sh` 无法发现后端启动失败 — **已修复**

- 严重程度：低
- 位置：`scripts/dev.sh`
- 修复说明：后台启动 uvicorn 后轮询 `/api/health`，进程退出或超时则报错退出，不再直接进入 `npm run dev`。
- 回归：脚本审查（无自动化 shell 测试）。

## 疑似缺陷

### S1. 预测帧仍进入逐帧平均速度 — **已修复**

- 严重程度：低
- 位置：`backend/processor.py`、`backend/traffic/traffic_metrics.py`
- 修复说明：非观测帧导出与展示的速度、加速度为 `None`；`traffic_metrics` 仅统计 `observed` 且速度有效的车辆。
- 回归：`tests/test_core.py::test_traffic_metrics_ignore_predicted_speeds`。

### S2. 车道趋势 `covered_seconds` 为空导致前端崩溃 — **已修复**

- 严重程度：低
- 位置：`backend/reports.py`、`frontend/src/components/LaneTrends.tsx`
- 修复说明：报告构建跳过缺少 `timestamp` / `window_seconds` 的车道行；表格对 `covered_seconds == null` 显示「—」。
- 回归：`tests/test_analysis_features.py::test_report_skips_lane_rows_with_missing_window`。

## 审计时另记：无 `frontend/dist` 时根路径 404 — **已修复**

- 修复说明：`backend/main.py` 在无 `frontend/dist` 时注册 `GET /`，返回 200 与构建/开发模式说明；`start.sh` / `setup.sh` 仍会构建前端。
- 回归：`tests/test_api.py::test_frontend_placeholder_when_dist_missing`（仅在仓库未带 dist 时运行）。

## 本次核对后未当作缺陷的部分（未改）

- 未标定时速度、世界坐标和速度类报警保持为空。
- 过线有限线段求交与单 ID 去重逻辑未改。
- WebSocket / HTTP 来源与 Host 边界、上传体积限制未改。
- 指标卡与画面极短帧差未单独列为缺陷。
