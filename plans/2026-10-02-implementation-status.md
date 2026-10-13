# 深度评审改进与验收记录

日期：2026-10-02。项目：基于视频感知的隧道交通数字孪生系统。依据：`plans/2026-10-02-deep-review.md` 中 R01–R18。原评审报告保留为修改前的证据；其中行号对应当时版本。

## 交付结论

R01–R17 对应的代码改进已实施；R18 增加人工真值评估工具和数据准备流程，真实准确性结论仍待素材、实测尺度与人工标注。依赖锁已接入安装脚本，但尚未联网验证干净安装；性能实现已减少重复工作，尚未完成长时录制的严格性能对照。当前仍为本机单会话系统。

此次修改没有训练模型，没有修改用户视频或已有实测标定，没有用默认尺度生成真实速度。后端回归、运行检查、模型加载检查、浏览器验收及默认 smoke 均使用隔离目录；原来的统计段与 `TEST_REPORT.json` 保留。前端生产构建已更新，重启后端并刷新页面即可使用。

## 按优先级落实

| 项目 | 优先级 | 实施内容与关键文件 | 验证及边界 |
| --- | --- | --- | --- |
| R01 来源保护 | P1 | `backend/security.py`、`backend/main.py`：WS 握手拒绝缺失/非可信 Origin；HTTP 修改请求校验浏览器来源；Host 限制本机 | 合法服务来源及 Vite 5173 可连接；外站与无 Origin WS 被拒；非法 Host/外站 POST 被拒。不是多人认证或公网部署方案 |
| R02 失败会话 | P1 | `backend/service.py`：新视频解码/配置准备成功后再替换旧会话；发布完成的状态；playing 无 processor 时转 error 并让出事件循环 | 注入新视频首帧失败后保留旧 reader、processor、token；无 processor 状态测试证明事件循环可继续执行 |
| R03 同帧绘制 | P1 | `frontend/src/utils/snapshotState.ts`、`hooks/useDecodedSnapshot.ts`、`VideoView.tsx`、`DigitalTwin.tsx`：解码后的 JPEG 与原快照成对提交，双画布使用共同显示状态 | 可控异步/乱序解码测试；实际 VideoView 绘制测试；浏览器横竖屏真实车辆与孪生观察 |
| R04 草稿归属 | P1 | `backend/api/schemas.py`、`backend/service.py`、`frontend/src/App.tsx`：video_token 与 scene_revision 防护，所有视频切换入口取消旧草稿 | 旧 token/旧道路修订 HTTP 409；浏览器保持未保存道路草稿后切换视频，面板关闭且出现取消提示 |
| R05 测试隔离 | P2 | `tests/conftest.py`、`tests/test_review_regressions.py`、`frontend/tests/snapshotState.test.mjs`；运行与 smoke 检查改用临时数据 | 后端 66 项、前端 15 项通过；关键流程另做真实浏览器验收。尚未建立完整 UI 端到端自动化套件 |
| R06 下载一致性 | P2 | `backend/exporter.py`：写入/flush/复制共用 RLock；`backend/main.py`：临时完整 CSV 响应，发送结束或失败后清理 | 活动分析下载验证 Content-Length 与内容一致；浏览器旧段下载 256 行、末帧 8.5 秒、累计流量 19 |
| R07 稀疏逆行 | P2 | `backend/events/rules.py`：窗口至少 0.7 秒，并按最近真实检测观测间隔扩展 | 0.1、0.5、1 秒观测间隔的逆行可触发；原有停车、急减速、冷却和未标定规则回归通过 |
| R08 网络顺序 | P2 | `frontend/src/utils/snapshotState.ts`：同会话忽略旧 revision，WS 接受新服务会话并拒绝已退役会话 | 延迟 HTTP 响应不能回退较新 WS 帧；服务重启后旧会话不能覆盖新会话 |
| R09 草稿保留 | P2 | `App.tsx`、`CalibrationPanel.tsx`：道路/参数分别提交，保存后面板保持打开；提交中禁用编辑字段 | 浏览器验证保存道路后置信度草稿仍为 0.5；应用参数后待保存的自动计数线仍保留；关闭明确提示放弃未保存更改 |
| R10 上传限额 | P2 | `backend/security.py`：ASGI 接收时统计请求体，2 GiB 视频 + 1 MiB multipart 开销，保留最终文件检查 | 有/无 Content-Length 超限返回 413；分块请求超限时已产生的 multipart 临时文件全部关闭 |
| R11 视频时间 | P2 | `backend/vision/video_reader.py`：逐帧解码 PTS；按帧索引探测 PTS 二分定位；末帧 PTS 推算末端；无效时间戳报错 | 实际 VFR MP4 的 PTS `[0, .12, .4, .84]` 通过，定位 .4 秒返回第 2 帧而非旧方式的 .84 秒。末帧时长仍按名义 FPS 近似；不能精确探测末端时标记 duration_estimated |
| R12 安装约束 | P2 | `requirements-locked-macos-py313.txt`、`scripts/lock_dependencies.py`、`scripts/setup.sh`：锁定项目自身完整依赖闭包，macOS arm64/Python 3.13 自动采用；其他平台明确兼容模式 | 本机项目依赖约束检查与脚本语法通过。当前 .venv 复用系统包，其他工具存在依赖冲突；没有重建或改动全局环境，没有干净安装验证，锁版本不含分发文件哈希 |
| R13 过线统计 | P2 | `backend/traffic/flow_counter.py`、`traffic_metrics.py`：最近分钟 deque 与全段累计计数/首末时间，移除每帧扫描整段穿越历史 | 200 次穿越测试保持总量 200、最近一分钟 60、平均时距 1 秒；完整真实视频计数仍为 19。ID 去重集合继续按全段保留 |
| R14 绘制开销 | P2 | `snapshotState.ts`：复用不变历史/类型引用；`Charts.tsx`：分开更新两个图表；`DigitalTwin.tsx`：观察器只随生命周期创建，尺寸改变才重建画布 | 引用稳定性测试、真实页面与窗口尺寸验收。未做长视频主线程 profile，不能声称固定比例的性能提升 |
| R15 权重信任 | P3 | `backend/vision/weights.py`、`detector.py`：三种权重统一流式 SHA-256 校验，SSD 显式加载本地 weights_only 文件 | 正确/损坏/缺失文件测试；三模型均完成真实抽查帧加载与推理。分析不自动下载权重；下载准备仍需联网 |
| R16 CLI 错误 | P3 | `scripts/analyze.py`：显式文件不存在即报错，场景 JSON/几何/画面边界验证，失败释放 reader，输出 run.json | 两个缺失参数测试、非法 JSON 测试；真实视频离线分析验证有效 scene、256 帧、段元数据和未标定 CSV |
| R17 绘制末点 | P3 | `VideoView.tsx`、`snapshotState.ts`：忽略双击的第二次 click、去重末点，使用“完成”按钮结束车道 | 点列回归测试与现有几何校验通过；README 使用按钮完成绘制 |
| R18 准确性评估 | P3 | 新增 `backend/evaluation.py`、`scripts/evaluate.py`、`examples/evaluation_truth.template.json`、`docs/accuracy-evaluation.md` | 工具与 8 项合成真值回归通过。输出计数误差、速度覆盖率/MAE/RMSE、报警一对一 TP/FP/FN/precision/recall；真实隧道准确率仍未评测；检测 mAP/MOT 尚需框/物理 ID 标注与结果导出 |

## 功能补充

- 历史统计段可从页面展开、分页、刷新并下载三类 CSV，切换视频和重新分析后仍能找到旧结果。
- 每段新增 `run.json` 保存视频内容哈希、时间边界、标定状态、参数和道路配置；旧目录缺少元数据时显示未记录，不推测来源。
- `TWIN_DATA_DIR` 支持另一套数据目录，测试使用临时目录；`TWIN_ALLOWED_ORIGINS` 可配置额外明确可信的浏览器来源。API 文档与 README 说明 token、修订冲突及命令行 WS Origin 要求。
- 字符串 CSV 字段防止直接以 Excel 公式前缀开头；数值负数仍按数值导出。配置与元数据 JSON 用临时文件替换，避免单文件半写入。

## 验收证据

本次最终命令与结果：

```text
.venv/bin/python -m pytest -q                  66 passed（包含实际 VFR/ffmpeg 检查）
npm --prefix frontend test                   15 passed
npm --prefix frontend run build              TypeScript + Vite 构建成功
bash -n scripts/setup.sh                     通过
.venv/bin/python scripts/lock_dependencies.py --check
                                              Project dependency constraints: PASS
.venv/bin/python scripts/check_runtime.py     HTTP + trusted-origin WS、正常退出、数据隔离 PASS
.venv/bin/python scripts/smoke_video.py --output docs/review-smoke-2026-10-02.json
                                              256 帧完整 CPU 分析 PASS
```

`scripts/check_runtime.py` 自动分配本机临时端口、生成 12 帧合成视频并检查服务退出，不需要用户演示素材或模型。原始 4K 桥梁素材 smoke 结果见 `docs/review-smoke-2026-10-02.json`：最多同时活动 13 辆、28 个确认 ID、最长 ID 保持 136 帧、测试线计数 19、无尺度测速及报警。42.5 FPS 是并行回归时的一次离线吞吐，非实时保证或严格优化对照；98.9% 相邻帧 ID 保留率不是有标注的跟踪精度。

模型抽查使用原视频 4 秒位置：VisDrone 检出 10 辆，COCO YOLO11n 与 SSD 各检出 0 辆。三种权重均校验并成功加载，通用模型的俯拍漏检仍存在，不能以“加载成功”解释为准确率改善。

浏览器通过内置浏览器真实操作 localhost:8002 的隔离系统：

1. 启动真实模型，竖屏素材分析至结束；打开道路面板暂停状态正常。
2. 清除计数线并保留置信度 0.5 草稿；保存道路后参数草稿不丢失。
3. 恢复自动线作为道路草稿，应用参数后道路草稿不丢失。
4. 编辑中切换到横屏视频，旧草稿取消并提示。
5. 展开历史记录并实际下载旧段交通统计 CSV，核验 256 行、8.5 秒末帧、流量 19、速度列留空。
6. 横屏素材开始/暂停，画布显示对应车辆 ID 与孪生轨迹；本次浏览器错误日志为空。
7. 桌面 1440×960、320×900 和 390×844 检查。320px/390px 文档宽度等于视口，无整页横向溢出；参数面板可访问。验收结束恢复视口并关闭测试服务。

截图：

- [桌面车辆与孪生](../output/playwright/review-desktop.jpg)
- [历史导出窄屏](../output/playwright/review-history-mobile.jpg)
- [320px 页面](../output/playwright/review-320.jpg)
- [390px 参数面板](../output/playwright/review-settings-390.jpg)

Playwright CLI 因 registry.npmmirror.com DNS 不可达未能启动，此次用内置浏览器执行上述检查。Vite 仍提示 charts chunk 约 545 kB；没有通过增大阈值隐藏这个提示。受网络限制未重新完成依赖漏洞在线扫描或干净依赖安装，不据此声称依赖安全无漏洞。

## 使用与下一阶段

执行 `./start.sh`，刷新页面。HTTP 校准和参数请求须带 `/api/state` 返回的 `video_token`；道路提交同时带 `scene_revision`，409 时重新打开当前视频面板取得最新配置。保存道路或参数会停止当前统计段，关闭编辑器后开始分析即可生成新段。

真实评测按 `docs/accuracy-evaluation.md` 准备素材、尺度依据和人工真值，再运行 `scripts/evaluate.py`。当前仍需完成：真实隧道准确性评估、检测/MOT 标注和导出、NVIDIA GPU 验收、全新环境安装，以及长视频前端/统计性能对照。多人独立任务、RTSP 接入/断线恢复和公网认证属于后续产品工作，未混入此次修复。
