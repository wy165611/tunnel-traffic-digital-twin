# 隧道系统改进 v2

分支：`feat/improve-v2`（基于 `main`）。本文汇总 v2 的功能、配置、接口与已知限制；v1 功能见 `docs/new-features-v1.md`。

## 1. 标定向导

- 三步向导：① 选择 P1–P4 角点（含顺序图）② 填写边 1→2 / 边 2→3 实测长度 ③ 鸟瞰确认后保存。
- P1→P2 为上边缘（通常横跨道路宽度），P2→P3 为右边缘（通常沿行车方向）。
- `frontend/src/utils/birdseye.ts` 用四点 Homography 还原俯视图，`BirdseyePreview` 按实测尺度绘制车道、虚拟线圈、计数线与 +Y 行车箭头。
- 未标定时后端 `EventDetector` 停用速度 / 跟车时距 / 排队米数组；`settings.calibration_available=false`，前端禁用相关输入并说明原因。

## 2. Webhook 鉴权、签名与投递日志

```yaml
alerts:
  webhook_enabled: false
  webhook_url: ''
  webhook_timeout_seconds: 3.0
  webhook_retries: 2
  cooldown_seconds: 10.0
  webhook_headers: {}           # 自定义 Header，不写入日志
  webhook_hmac_secret: ''       # 非空时启用签名
  webhook_hmac_header: X-Twin-Signature
```

- 自定义 Header：原样附加；`Content-Type`、`Content-Length`、`Host` 不可覆盖，含换行的非法名称/值被忽略。
- HMAC：设置密钥后发送 `X-Twin-Timestamp`（Unix 秒），签名为：

  ```text
  X-Twin-Signature: sha256=<hex(HMAC_SHA256(secret, "<timestamp>.<原始 JSON body>"))>
  ```

  每次重试重新生成时间戳和签名。
- 投递日志：`GET /api/webhook-log?limit=50&offset=0&status=all|success|failed`，返回事件 ID、尝试次数、HTTP 状态码或错误类型、时间。
- 日志为进程内环形缓冲（最多 500 条），不记录 URL、密钥或 Header 值；进程重启后清空。
- 现有 daemon 线程、单次超时、0.2/0.4 秒退避重试均保留；失败不影响分析、CSV 与证据。
- **已知限制：未做防重放。** 系统只发送，不实现接收端验签与时间窗口校验；接收端应比较 `X-Twin-Timestamp` 与当前时间并拒绝过期或重复签名。

## 3. 实时流分辨率变化

- 重连成功后比较新流宽高；变化时置 `video.resolution_changed=true`，记录 `video.resolution_change={previous,current}`。
- 帧仍缩放到原显示尺寸，保持像素坐标空间一致；但原标定视为失效：
  - `settings.calibration_available=false`，`processor` 收到 `calibration=None`；
  - 测速、跟车时距、排队米数、密度、服务水平整组停用；
  - 状态快照下发 `calibration_notice`，前端顶部与标定面板提示“分辨率变化，请重新标定”。
- 重新保存标定（`POST /api/calibration`）后清除标记并恢复指标。

## 4. 静止异物 / 抛洒物启发式

- 新增 `backend/events/debris.py`，复用每车道虚拟线圈：
  1. 对灰度帧做背景差分（含选择性背景更新，静止前景不被吸收）；
  2. 计算线圈内前景面积占比；
  3. 占比超过阈值且圈内没有观测车辆，持续达到设定秒数后产生 `ROAD DEBRIS`（路面异物）事件；
  4. 每车道独立冷却，避免重复告警。
- 事件写入 `events.csv`、证据截图与 `capture.json`，并走 Webhook；`vehicle_id=-1`，证据框为线圈外接框。
- 无车道 / 无线圈时不启用；纯图像启发式，不依赖道路尺度标定。

```yaml
events:
  debris_enabled: true
  debris_seconds: 2.0
  debris_area_ratio: 0.18
  debris_difference_threshold: 30
  debris_cooldown_seconds: 30.0
```

## 5. 顺手修复

- **默认模型与闯入检测**：保留 VisDrone 默认模型，`intrusion_enabled` 默认改为 `false`；UI 提示默认 VisDrone 不含 `person/bicycle`，如需闯入检测请切换 COCO 并勾选。
- **直播证据**：`capture.json` 增加 `source.live=true`；证据弹窗与导入弹窗明确“直播仅保存触发截图，不提供原视频回放”。
- **RTSP**：优先 `rtsp_transport=tcp`（合并 `OPENCV_FFMPEG_CAPTURE_OPTIONS`），通过 `CAP_PROP_OPEN_TIMEOUT_MSEC / CAP_PROP_READ_TIMEOUT_MSEC` 限制打开/读取（`video.stream_open_timeout_seconds`、`stream_read_timeout_seconds`，默认 8/10 秒），重连复用同一逻辑。
- **文档**：`docs/features-analysis.md` 明确时间占有率已启用；`docs/new-features-v1.md` 同步 v2 限制。

## 6. 已知限制

- 未实现 Webhook 接收端验签、时间窗口与幂等去重，**未做防重放**；投递日志不持久化。
- 分辨率变化后保留旧坐标空间，宽高比变化时画面会被拉伸；必须重新标定才能恢复米制指标。
- 路面异物为背景差分启发式：光照突变、阴影、长期停放且未被检测器识别的车辆可能误报；不能区分异物类别，也不能识别烟火。
- 默认 VisDrone 模型不含行人和非机动车类别；启用闯入检测需切换 COCO 模型。
- 仍无 RTSP 认证重试、码流切换、录像回放与断流持久化队列；超时参数依赖 OpenCV/FFmpeg 构建版本。
