# 隧道系统改进 v2 — 进度与交接

分支：`feat/improve-v2`（基于 `main` 7069c32）
远端：https://github.com/wy165611/tunnel-traffic-digital-twin/tree/feat/improve-v2

## 已完成并推送

- `7a803ff` docs: add task description for tunnel improvements v2
- `d8903fe` feat(calibration): add guided wizard with bird's-eye preview and metric gate

### 主需求 1 — 标定向导（已完成）

- 三步向导：① 选择 P1–P4 角点（含顺序示意图）② 填写边 1→2 / 边 2→3 实测长度（注明 P1→P2 上边缘、P2→P3 右边缘语义）③ 鸟瞰确认后保存。
- 视频画面标注 P1–P4 及 `1→2 · x m`、`2→3 · y m`。
- 新增 `frontend/src/utils/birdseye.ts`（四点 Homography 求解/投影）与 `frontend/src/components/BirdseyePreview.tsx`（按实测尺度绘制车道、虚拟线圈、计数线、+Y 行车箭头）。
- 未标定时后端 `EventDetector` 显式停用速度/时距/排队规则组，`settings.calibration_available` 与 `calibration_required_metrics` 下发前端；CalibrationPanel 禁用相关输入并显示原因，Dashboard/服务水平/排队长度文案同步。
- 测试：`tests/test_calibration_gate.py`（3 项）、`frontend/tests/birdseye.test.mjs`（5 项）。

## 未完成（按任务原文顺序）

### 主需求 2 — Webhook 鉴权与投递日志（未开始）

- 支持 `alerts.webhook_headers` 自定义 Header；支持 `webhook_hmac_secret` + 可配置签名 Header，对原始 JSON body 做 HMAC-SHA256（`sha256=<hex>`）。
- 保留现有 daemon 线程、单次超时与 `webhook_retries` 重试；每次投递结果（成功/失败、尝试次数、状态码/错误、事件 ID）追加写入可查询日志。
- 计划落点：`backend/alerts.py`、`backend/processor.py`、`backend/main.py`（`GET /api/webhook-log?limit&offset&status`）、`config.yaml`、`tests/test_alerts.py` 或新测试；日志不得记录密钥或自定义 Header 值。

### 主需求 3 — 流分辨率变化提示与指标停用（未开始）

- `VideoReader` 重连时比较新流宽高；变化时置 `resolution_changed` 并记录旧/新尺寸，保留原坐标空间缩放以维持管线一致。
- `AnalysisService` 检测到该标记后提示“请重新标定”，将标定视为失效（processor 传 `calibration=None`），停用测速/跟车时距/排队米数/密度/服务水平；重新保存标定后清除。
- 前端状态条/标定面板显示提示；补 `tests/test_stream.py` 或新测试。

### 主需求 4 — 静止异物/抛洒物启发式（未开始）

- 新增 `backend/events/debris.py`：基于虚拟线圈 ROI 的前景持续占用 + 非车辆判据（观测车辆在圈内时抑制）；持续时间、面积比、冷却可配。
- 事件名建议 `ROAD DEBRIS`（路面异物），写入 events.csv/证据/Webhook；无车道线圈时不启用。
- 配置加入 `config.yaml → events`、`RuntimeSettings`、CalibrationPanel 分析参数；补 `tests/test_debris.py`（触发、车辆抑制、冷却、阈值）。

### 顺手修 A — 默认模型与闯入检测错配（未开始）

- 已定方案：保留 VisDrone 默认模型（适配俯拍车辆），将 `config.yaml` 与 `RuntimeSettings.intrusion_enabled` 默认改为 `false`，UI 明确提示“默认 VisDrone 不含 person/bicycle；如需闯入检测请切换 COCO 并开启”。

### 顺手修 B — 直播证据仅截图提示（未开始）

- `capture_event` 来源元数据增加 `live`；EvidenceDialog 对直播事件显示“直播仅保存触发截图，不提供原视频回放”；导入弹窗流地址说明同步。

### 顺手修 C — RTSP 打开超时与 TCP 优先（未开始）

- `VideoReader` 打开流时优先 `rtsp_transport=tcp`（合并 `OPENCV_FFMPEG_CAPTURE_OPTIONS`），通过 `cv2.VideoCapture(..., CAP_FFMPEG, [OPEN_TIMEOUT_MSEC, READ_TIMEOUT_MSEC])` 限制打开/读取；重连复用同一逻辑，超时可配置。
- 更新 `tests/test_stream.py` 的 FakeCapture 以接受参数并断言 TCP 与超时。

### 顺手修 D — 文档（未开始）

- `docs/features-analysis.md`：时间占有率已启用（默认开启，可在分析参数关闭），删除“仍未启用”表述。
- `docs/new-features-v1.md`：更新 Webhook 鉴权/日志、RTSP TCP 与超时、分辨率变化、静止异物、直播仅截图、默认闯入关闭等已知限制。
- 建议补 `docs/improvements-v2.md` 汇总 v2 功能与限制。

## 验收未完成

- [ ] 全量 `pytest` 全绿（当前基线：141 passed, 1 skipped——`frontend/dist` 存在导致构建断言跳过）
- [ ] `npm test` 全绿（当前 57 passed）
- [ ] `npm run build` 通过
- [ ] 开 PR 到 `wy165611/tunnel-traffic-digital-twin`（`feat/improve-v2` → `main`，不要合 PR #6）
- [ ] 写 `/workspace/qoder-tasks/tunnel-improve-v2-RESULT.md`（分支、PR 链接、测试数、改动摘要、已知限制）
- [ ] 每完成一项 commit + push 一次；单次写入不超过 150 行

## 本地验证环境

```bash
cd /workspace/tunnel-traffic-digital-twin
.venv/bin/python -m pytest -q
cd frontend && npm test && npm run build
```
