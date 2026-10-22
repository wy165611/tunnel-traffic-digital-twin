# 任务：隧道系统改进 v2
仓库：/workspace/tunnel-traffic-digital-twin。先 git checkout main && git pull，从 main 开分支 feat/improve-v2。不要合 PR #6。每次写入不超过 150 行。
## 主需求
1. 标定向导：鸟瞰预览；角点顺序和边长语义写清楚；未标定时整组关掉测速、跟车时距、排队米数，并在 UI 说明原因。
2. Webhook 鉴权：支持自定义 Header 和/或 HMAC 签名；投递失败写入可查询的日志；保留现有异步超时与重试。
3. 流分辨率变化时提示重新标定，并停用依赖标定的指标。
4. 静止异物/抛洒物：启发式，虚拟线圈短时被占用且非车辆时告警；阈值和冷却可配；有测试。
## 顺手修
A. config.yaml 默认 visdrone 模型与闯入检测错配：默认改 COCO 或默认关闯入并提示。
B. 直播证据：UI 写清「直播仅截图」。
C. RTSP VideoCapture 打开超时，优先 rtsp_transport=tcp。
D. 更新 docs/features-analysis.md（占有率已启用）和 docs/new-features-v1.md 已知限制。
## 验收
pytest 全绿；前端测试全绿；构建通过；开 PR 到 wy165611/tunnel-traffic-digital-twin；写 /workspace/qoder-tasks/tunnel-improve-v2-RESULT.md（分支、PR 链接、测试数、改动摘要、已知限制）。
