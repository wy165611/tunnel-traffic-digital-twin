# 缺陷审计报告

审计日期：2026-10-13。范围是仓库根目录的后端、前端、脚本、`config.yaml` 与 `models.json`。  
**修复批次：2026-10-13**（分支 `cursor/bug-audit-report-1d52`）。下列条目均已在本分支修复，并补充回归测试（见各条「修复说明」）。

## 2026-10-18 第二批审计修复（M1 / M2 / L1–L7）

- 分支：`fix/audit-m1-m2-l1-l7`
- 代码提交：`c9b0e2a`
- PR：[#2](https://github.com/wy165611/tunnel-traffic-digital-twin/pull/2)
- 来源：`/workspace/tunnel-traffic-digital-twin-bug-report.md`（2026-10-18 只读审计）

| 条目 | 状态 | 修复说明 | 回归测试 |
| --- | --- | --- | --- |
| M1 标定角点顺序拒绝合法斜向凸四边形 | **已修复** | `backend/calibration/homography.py`：不再按 y/x 排序反推 TL/TR；只校验凸性与图像坐标顺时针（有向面积），第一个点作为左上角。 | `tests/test_core.py::test_calibration_accepts_diagonal_clockwise_quad_and_uses_first_point_as_top_left`、`test_calibration_rejects_wrong_corner_order` |
| M2 宽/长语义与画面方向绑定 | **已修复（UI 最小改动，待 owner 确认设计）** | `frontend/src/components/CalibrationPanel.tsx` 改为「边 1→2 实测长度 / 边 2→3 实测长度」，并提示分别对应第 1、2 点与第 2、3 点之间的实际距离；README 同步。后端 `width_m` / `length_m` 字段与 homography 数学未改，未自动推断 `legal_direction`。 | `tests/test_core.py::test_calibration_edge_1_2_and_2_3_map_to_supplied_lengths` |
| L1 前端先解析 JSON 再判断 `ok` | **已修复** | `frontend/src/api.ts` 新增 `parseApiResponse`：先读 `text()`，容错 JSON；422 `detail` 数组格式化为可读文本；纯文本/HTML 错误回退到状态文本。`App.tsx` 上传路径复用。 | `frontend/tests/api.test.mjs` 新增 4 条 |
| L2 帧数未知或偏大时 seek 失败 | **已修复** | `backend/vision/video_reader.py`：`frames<=0` 回退 `CAP_PROP_POS_MSEC`；索引探测失败时收缩上界，必要时定位到最后一个可解码帧。 | `tests/test_video_timing.py::test_seek_clamps_to_last_decodable_frame_when_count_is_overreported`、`test_seek_falls_back_to_msec_when_frame_count_is_zero` |
| L3 实时流（RTSP）路径不可用 | **已修复** | `backend/service.py`：live 预览不调用 seek，也不回绕；`frames=0` 不再让每次 play 触发重置；live seek 明确返回「实时流不支持拖动」。 | `tests/test_api.py::test_live_preview_does_not_seek_or_rewind`、`test_live_play_does_not_reset_processor_when_frame_count_is_unknown` |
| L4 导入/上传异常时文件残留 | **已修复** | `backend/main.py`：导入与上传均用 `finally` 在未成功时清理临时文件；`ValueError`/`OSError` 仍映射 400，其他异常（如 `cv2.error`）返回 500 但文件已清理。 | `tests/test_api.py::test_upload_and_import_cleanup_on_unexpected_select_failure` |
| L5 模板场景缺键返回 500 | **已修复** | `backend/camera_templates.py`：`template_value` 要求 `scene.counting_line` 存在且 `scene.lanes` 为列表，损坏模板按不存在处理（404）。 | `tests/test_camera_templates.py::test_template_with_missing_scene_keys_is_treated_as_corrupt` |
| L6 `交付/` 下为修复前旧代码 | **已标记，未重建** | 新增 `交付/源码包状态说明-请先阅读.md`，明确目录与 zip 都是旧快照、禁止直接交付，并列出缺失的修复；**未删除任何交付物**。 | 文档说明 |
| L7 Canvas `roundRect` 兼容性 | **已修复** | 新增 `frontend/src/utils/canvasShape.ts`；`DigitalTwin.tsx` 检测 `ctx.roundRect`，不支持时回退 `ctx.rect`。 | `frontend/tests/canvasShape.test.mjs` 新增 2 条 |

测试结果（2026-10-18，Python 3.13.5 / Node.js 20.19.2）：

| 检查 | 结果 |
| --- | --- |
| `pytest -q` | **104 passed**（原 96，新增 8） |
| `npm --prefix frontend test` | **38 passed**（原 32，新增 6） |
| `npx tsc -b` | 通过 |
| `npm --prefix frontend run build` | 通过 |

需 owner 决策：M2 只改了 UI 文案，未确认「按道路方向自动设置合法方向」是否属于预期设计；L6 未重建交付包。

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
