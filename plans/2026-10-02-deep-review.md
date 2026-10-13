# 项目深度评审报告

评审日期：2026-10-02  
范围：Python / FastAPI / OpenCV / PyTorch 后端、React / TypeScript 前端、测试、依赖配置、脚本与产品文档。此目录原先不存在。本工作区没有 Git 元数据，因此无法记录评审所对应的提交号；报告按本次只读检查的工作区内容编写。

## 结论

这是一个边界诚实、可本机运行的小型演示系统。README 对预训练模型来源、未标定时不输出真实速度、短视频指标限制、单共享会话及 RTSP 未开放到 UI 均有说明；实现也有 API 输入校验、显式视频路径检查、模型下载摘要校验和多组几何/跟踪/导出测试。本次没有发现凭代码可确认的硬编码秘密。项目已有覆盖能力，但有几处失败和并发路径没有纳入现有回归测试。

最该先处理的是：WebSocket 对跨来源请求没有检查、播放状态出错时会忙循环卡住后端、视频画面可能短暂配上另一个帧的检测框，以及编辑视频切换后可能保存错误视频的道路配置。另有活动 CSV 下载竞争、特定检测间隔让逆行规则静默失效等较窄问题。

## 发现与优先级

下表按影响、修复成本、置信度与修复风险综合排序。P1 表示可能暴露本机敏感画面，或让主要工作流/整个服务失效；P2 表示部分输入或时序下结果会错误、数据会受损，或常用路径不可靠；P3 表示局部体验、维护或性能机会。成本：S 为数小时，M 为约一天，L 为多日，均含合理回归检查。

| ID | 优先级 | 发现 | 类别 | 成本 / 修复风险 | 置信度 | 证据 |
|---|---|---|---|---|---|---|
| R01 | P1 | 限制 WebSocket 握手来源 | 安全 | S / 低 | 高（服务器无检查；浏览器可达性依浏览器） | [main.py:147](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/main.py:147)、[service.py:30](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/service.py:30) |
| R02 | P1 | 清理播放与视频切换失败状态，避免事件循环空转 | Bug / 架构 | M / 中 | 高，已复现 | [service.py:60](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/service.py:60)、[service.py:175](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/service.py:175) |
| R03 | P1 | 将图像帧与该帧车辆状态一起绘制 | Bug | M / 中 | 高，内存复现 | [App.tsx:22](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:22)、[VideoView.tsx:34](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/VideoView.tsx:34) |
| R04 | P1 | 视频切换时让未保存的编辑草稿失效 | Bug / 数据完整性 | M / 中 | 高，代码路径确认 | [App.tsx:33](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:33)、[App.tsx:36](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:36)、[service.py:143](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/service.py:143) |
| R05 | P2 | 为交互关键路径补上前端测试，并隔离后端测试输出 | 测试 | M / 低 | 高，现状可见 | [package.json:6](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/package.json:6)、[twinGeometry.test.mjs:6](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/tests/twinGeometry.test.mjs:6)、[test_core.py:152](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/tests/test_core.py:152)、[exporter.py:17](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/exporter.py:17) |
| R06 | P2 | 对活动 CSV 提供稳定快照后再下载 | Bug / 并发 | M / 中 | 高，已复现长度竞态 | [processor.py:114](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/processor.py:114)、[processor.py:129](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/processor.py:129)、[main.py:137](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/main.py:137) |
| R07 | P2 | 按实际检测观测间隔运行逆行检查 | Bug | M / 中 | 高，内存复现 | [rules.py:37](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/events/rules.py:37)、[schemas.py:64](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/api/schemas.py:64) |
| R08 | P2 | 丢弃旧 revision 的网络状态 | Bug / 前端状态管理 | M / 中 | 高（缺少顺序防护；实际乱序尚未注入） | [App.tsx:22](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:22)、[App.tsx:25](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:25)、[types/index.ts:10](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/types/index.ts:10) |
| R09 | P2 | 单独保存参数或道路后保留另一份草稿 | Bug / 交互 | M / 中 | 高（产品是否接受自动舍弃需维护者决定） | [CalibrationPanel.tsx:8](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/CalibrationPanel.tsx:8)、[CalibrationPanel.tsx:22](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/CalibrationPanel.tsx:22)、[App.tsx:33](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:33) |
| R10 | P2 | 在 multipart 解析期间施加上传总量上限 | 安全 / 资源限制 | M / 中 | 高，已核对正在使用的框架路径 | [main.py:82](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/main.py:82)、[main.py:93](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/main.py:93) |
| R11 | P2 | 确认录制输入的时间戳，或拒绝可变帧率输入 | 正确性 | M / 中 | 高（代码假设明确；当前素材是否受影响未核） | [video_reader.py:25](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/vision/video_reader.py:25)、[video_reader.py:50](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/vision/video_reader.py:50)、[speed_estimator.py:18](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/traffic/speed_estimator.py:18) |
| R12 | P2 | 让安装脚本采用可复现的 Python 依赖约束 | 依赖 / DX | M / 中 | 高 | [setup.sh:5](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/scripts/setup.sh:5)、[requirements.txt:1](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/requirements.txt:1)、[requirements-verified.txt:1](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/requirements-verified.txt:1) |
| R13 | P2 | 用滑动窗口维护过线流量和平均时距 | 性能 | S–M / 低 | 高（复杂度确定；当前视频未显现压力） | [flow_counter.py:10](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/traffic/flow_counter.py:10)、[flow_counter.py:35](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/traffic/flow_counter.py:35)、[traffic_metrics.py:13](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/traffic/traffic_metrics.py:13) |
| R14 | P2 | 仅在历史或类型数据改变时更新图表 | 性能 | M / 低–中 | 高（冗余工作可见；实际收益需测量） | [Charts.tsx:14](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/Charts.tsx:14)、[DigitalTwin.tsx:8](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/DigitalTwin.tsx:8)、[processor.py:131](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/processor.py:131) |
| R15 | P3 | 在加载本地 YOLO 权重时核对 manifest 摘要 | 安全 / 供应链 | S / 低 | 高（仅下载时摘要校验） | [download_models.py:13](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/scripts/download_models.py:13)、[detector.py:44](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/vision/detector.py:44) |
| R16 | P3 | 拒绝 CLI 显式指定但不存在的标定或场景文件 | 正确性 / DX | S / 低 | 高，回退行为可从代码确认 | [analyze.py:26](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/scripts/analyze.py:26)、[analyze.py:29](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/scripts/analyze.py:29)、[homography.py:33](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/calibration/homography.py:33) |
| R17 | P3 | 避免结束车道绘制时写入双击产生的重复点 | Bug / 交互 | S / 低 | 高，几何校验可确认结果 | [VideoView.tsx:37](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/VideoView.tsx:37)、[App.tsx:31](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:31)、[schemas.py:33](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/api/schemas.py:33) |
| R18 | P3 | 为真实道路与隧道样本建立准确性评估流程 | 功能 / 方向 | L（粗估） / 中 | 高（需求边界明确） | [README.md:245](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/README.md:245)、[README.md:249](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/README.md:249)、[TEST_REPORT.json](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/TEST_REPORT.json) |

## 重要发现详情

### R01：限制 WebSocket 握手来源（P1，安全）

后端在 [main.py:147](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/main.py:147) 接受任何 `/ws` 握手，并推送 `service.state()`；其中包括视频 JPEG、视频标识、场景和分析设置。[service.py:30](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/service.py:30) 与 [service.py:76](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/service.py:76) 可见返回内容。绑定 loopback 缩小了网络暴露面，但代码本身没有浏览器来源边界。本次用测试客户端带另一个 Origin 建立连接，服务仍接受并发送帧；这确认了服务端缺少来源校验，不等同于验证所有浏览器上的攻击可达性。建议明确允许的应用来源，保留本地生产地址与开发地址，并测试允许和拒绝的握手。OWASP 的 [WebSocket 安全指南](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html#origin-header-validation) 建议使用明确的来源白名单。修复风险低，需避免过宽通配规则。

### R02：失败后恢复一致的播放状态（P1，正确性与服务可用性）

[service.py:60](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/service.py:60) 到 [service.py:67](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/service.py:67) 关闭旧处理器并替换 reader，之后才读取新视频第一帧；若第一帧不能解码，[preview_sync](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/service.py:69) 抛出异常而服务状态仍可能是 `playing`。此时处理器为 `None`。[service.py:181](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/service.py:181) 到 [service.py:183](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/service.py:183) 在该状态直接 `continue`，跳过事件循环休眠。配置应用后预览失败也会进入相同分支。本次以假 reader 和有界异步循环复现：已排队的事件循环回调在连续 1000 次忙循环中一次也未运行。实际后果是 API、WebSocket 和正常关停都可能卡住。先准备并验证新 reader 和预览帧，再原子交换会话；失败时回到可恢复的暂停/错误状态，且保证循环分支让出事件循环。需测试首帧损坏、失败后控制请求仍可响应，以及关停。

### R03：同步视频帧和叠加数据（P1，核心功能正确性）

[App.tsx:22](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:22) 在每次 WebSocket 快照到达时同时更新状态与场景引用。[VideoView.tsx:34](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/VideoView.tsx:34) 异步解码 JPEG，但 [VideoView.tsx:35](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/VideoView.tsx:35) 也会因场景引用变化调用绘制；绘制逻辑把最新车辆状态叠到单独保留的上一张 `Image` 上。本次用延迟 `Image.onload` 的内存桩复现：屏幕先出现帧 1 图像与帧 2 检测框，尽管孪生视图已显示帧 2。对于强调真实视频与孪生同步的产品，这会误导位置判断。建议让解码后的图像与对应快照成组提交、旧解码完成时丢弃过期快照，再为快速切帧、暂停及编辑预览加组件测试。修复时需权衡慢速解码时的画面更新速度。

### R04：编辑草稿绑定到具体视频（P1，配置数据完整性）

编辑中，[App.tsx:22](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:22) 会阻止新快照更新本地道路与标定草稿；已有视频选择路径 [App.tsx:38](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:38) 会清理编辑状态，但上传和路径导入 [App.tsx:36](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:36) 与 [App.tsx:37](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:37) 成功后不会清理。保存请求又没有携带草稿对应的视频身份；服务按当前 identity 写入配置，见 [service.py:143](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/service.py:143) 到 [service.py:151](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/service.py:151)。所以用户可在 A 的草稿仍开着时导入 B，之后将 A 的图形写入 B。给草稿记录当前视频身份，统一处理所有切换入口；后端保存时核对目标身份。验证上传、路径导入、已有视频选择及共享会话被另一浏览器切换的路径。

### R05：测试应保护 UI 状态与用户数据（P2，测试）

前端 `npm test` 只发现几何工具测试：[package.json:6](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/package.json:6)、[twinGeometry.test.mjs:6](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/tests/twinGeometry.test.mjs:6)。上述画面解码、HTTP 与 WebSocket 到达顺序、视频切换和编辑保存都没有覆盖。后端测试 [test_core.py:152](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/tests/test_core.py:152) 直接创建会写文件的 `TrafficProcessor`；生产写出目录来自 [exporter.py:17](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/exporter.py:17)。因此 README 中直接运行的 pytest 命令会把测试 CSV 混入用户历史分析。用前端可控解码与网络 mock 做关键状态回归，并将所有生成物导向临时目录、用 `finally` 关闭导出器。另有运行脚本将默认视频恰为 256 帧作为断言，见 [check_runtime.py:26](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/scripts/check_runtime.py:26)；建议改用固定临时视频和动态端口，避免依赖用户素材。

### R06：导出正在写入的 CSV 时建立稳定快照（P2，竞态）

处理器每帧追加车辆与统计行，并在 [processor.py:130](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/processor.py:130) 刷新文件；同一 run 可在播放时下载，见 [main.py:137](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/main.py:137) 及 [DataExportPanel.tsx:10](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/DataExportPanel.tsx:10)。Starlette 在读取前先设置 `Content-Length`，之后才打开文件；本次在临时目录用同一时序复现，响应声明 7 字节而实际读到 9 字节。生产中持续追加可能造成客户端下载截断或 HTTP 长度错误。对下载实现一致的快照/短锁，或只开放已结束统计段的正式文件；测试播放中下载、暂停后下载和结束后下载。修复要避免阻塞逐帧 CSV 写入。

### R07：逆行检测窗口适应稀疏观测（P2，算法）

逆行判断仅读取最近 0.7 秒的世界坐标轨迹、至少需要两个点，见 [rules.py:37](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/events/rules.py:37) 到 [rules.py:43](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/events/rules.py:43)。设置允许检测间隔 10 帧，[schemas.py:64](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/api/schemas.py:64)；10 FPS 片段由此只产生每秒一个观测。处理器只在观测帧更新轨迹和规则，见 [processor.py:74](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/processor.py:74) 与 [processor.py:106](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/processor.py:106)。实际内存轨迹上持续 36 km/h 逆行 5 秒，规则发出 0 条事件；0.1 秒观测间隔则触发事件。按观测间隔推导采样窗口、加入有效观测连续性判断，或限制该设置组合；回归用不同 FPS 与 detection_interval 覆盖转弯和连续逆行，避免单纯放宽窗口带来误报。

### R08、R09：网络顺序与编辑草稿（P2，状态管理）

页面同时请求初始 `/state`、接 WebSocket 并处理写操作的 HTTP 响应。[App.tsx:25](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:25) 到 [App.tsx:28](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:28) 对所有响应无条件调用 `accept`，尽管 Snapshot 已带 `revision`。旧 HTTP 响应后到时会回退帧、视频或状态。跟踪同一服务实例的 revision 可解决此问题，但后端重启后需识别新会话并重置版本基线。另有参数草稿单独保存在 CalibrationPanel 的局部 state，而道路草稿在 App 中维护；“应用参数”和“保存道路”都会关闭整个面板，见 [CalibrationPanel.tsx:8](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/CalibrationPanel.tsx:8)、[CalibrationPanel.tsx:22](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/CalibrationPanel.tsx:22) 与 [App.tsx:33](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:33) 至 [App.tsx:34](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:34)。用户交替调整两类设置再单独保存时，后保存一类会卸载另一类未保存草稿。加入 dirty 状态提示，或让保存成功后保留尚未提交的另一份草稿；明确保存 API 的目标视频与配置范围。

## 其余问题与机会

- **R10，上传大小限制（P2，安全/资源）**：[main.py:83](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/main.py:83) 中的 2 GB 判断发生在业务层拿到 `UploadFile` 之后。当前安装的 FastAPI/Starlette 会先解析 multipart 文件并写临时存储；框架的 `max_part_size` 限制普通字段，不限制文件 part。因此超限上传消耗临时磁盘后才被业务拒绝。限制需在 ASGI 接收请求体时执行，同时保留业务检查及失败清理，并用小型可调阈值测试，不必创建大文件。高置信，M 成本、中风险。若服务只供自己本机使用，主要影响是磁盘占满；若可从其他站点或设备访问，优先级更高。
- **R11，可变帧率输入（P2，正确性）**：[video_reader.py:25](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/vision/video_reader.py:25)、[video_reader.py:50](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/vision/video_reader.py:50) 用单一 FPS 计算时间戳、时长和 seek 帧号；速度估计再据该时间求导。若导入可变帧率片段，即使道路标定正确，速度、加速度及事件持续时间仍可能偏移。使用解码时间戳，或在导入时识别并说明只接受 CFR；以非均匀时间戳合成运动测试。实现假设置信度高，现有用户视频是否触及此条件尚未核验，M 成本、中风险。
- **R12，依赖锁定（P2，DX/可维护性）**：`setup.sh` 安装范围版本的 `requirements.txt`，但 `requirements-verified.txt` 未被安装脚本使用，且没有传递依赖锁定。当前虚拟环境启用了 system-site-packages。新电脑重复安装可能得到不同组合，登记的验收版本也不能独立重建。定义受支持的 Python/平台和 CPU/GPU 安装路径，再选择约束文件或完整锁定；不要将共享系统环境简单 freeze 进项目。M 成本、中风险。
- **R13，过线历史复杂度（P2，性能）**：每帧用整段 `crossings` 重新计算一分钟窗口以及所有间隔的平均值，[flow_counter.py:35](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/traffic/flow_counter.py:35)、[traffic_metrics.py:13](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/traffic/traffic_metrics.py:13)。累计穿越数增加后，逐帧统计开销按历史长度增长。窗口用 deque、全段平均时距用累计值可保留现有口径；以长视频与大量穿越计数比较结果和吞吐。高置信，S–M 成本、低风险；当前 8.5 秒样本不足以说明实际卡顿。
- **R14，前端热路径重复工作（P2，性能）**：WebSocket 每帧更换 `history`/`types` 引用，使 Charts 每帧映射完整历史并向两个图表重复设置选项；DigitalTwin 每帧重建 ResizeObserver 并重置 canvas backing store。[Charts.tsx:14](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/Charts.tsx:14)、[DigitalTwin.tsx:8](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/DigitalTwin.tsx:8)、[processor.py:131](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/processor.py:131)。把观察器绑定到组件生命周期，尺寸实际变化时才调整 canvas，只在指标或历史采样变化时更新图表；先用长片段 profile 判断收益。高置信存在冗余，中置信性能收益，M 成本、低到中风险。
- **R15，本地权重运行时摘要（P3，供应链维护）**：下载脚本对模型 manifest 中摘要做校验，但 YOLO 启动路径仅检查文件存在；SSD 使用 Torchvision 默认权重路径。[download_models.py:13](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/scripts/download_models.py:13)、[detector.py:26](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/vision/detector.py:26)、[detector.py:44](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/vision/detector.py:44)。发现本机 YOLO 权重损坏或被替换时，运行时不会用同一 manifest 主动拒绝。本地 PyTorch 权重反序列化是代码信任边界，但没有发现远程替换接口，不应表述成远程代码执行漏洞。统一 manifest 运行时校验、拒绝非预期自动获取；缺失/损坏/匹配摘要测试。S 成本、低风险、高置信。
- **R16，显式 CLI 路径错误（P3，DX）**：`analyze.py` 对用户显式给出的 `--calibration` 路径调用 `RoadCalibration.load`，若文件不存在则返回 `None`；错误路径会静默退回未标定分析并导出空速度。[analyze.py:26](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/scripts/analyze.py:26)、[homography.py:33](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/calibration/homography.py:33)。区分自动查找的可选默认文件与显式传入路径；后者不存在或 JSON 无效时直接给出文件路径错误。补 CLI 参数边界测试。S 成本、低风险、高置信。
- **R17，双击结束车道绘制（P3，前端 Bug）**：画布 click 先追加点，双击事件又调用结束；车道结束时没有去重末点。[VideoView.tsx:37](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/components/VideoView.tsx:37)、[App.tsx:31](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/frontend/src/App.tsx:31)。双击末点会生成零长度末边，并触发后端凸性校验拒绝；后端拒绝几何的规则见 [schemas.py:33](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/backend/api/schemas.py:33)。可统一移除这一快捷结束行为，或忽略双击触发的末次 click；加入点列测试。S 成本、低风险，高置信。
- **R18，建立真实样本准确性评估（方向，P3）**：README 明确实际速度仍需道路测量、隧道画面仍需样本验证，[TEST_REPORT.json](/Users/wanghaoxin/Desktop/基于视频感知的隧道交通数字孪生系统/TEST_REPORT.json) 也说明当前跟踪连续性不是人工标注后的 ID-switch/准确率指标。可先设计一套小型经授权样本与人工真值流程，分别报告检测、计数、速度误差和报警误报，再决定是否投入隧道模型适配。这会提升竞赛展示结论的可信度，但需要标注时间和多场景素材；建议先写评估设计/样本要求，而非直接训练模型。粗估 L，决策置信度高。
- **方向：历史统计段可检索**：后端已有 `/api/runs`，README 表示重播/保存配置后旧 CSV 会保留；但导出 UI 只呈现当前 run。可增加历史段目录及三种 CSV 下载，再根据用户是否需要跨段对比设计可识别元数据，避免第一步就扩展成数据库。粗估 M，有直接代码与文档依据；属于便利功能，不是现有功能失效。

## 验证、范围与限制

- 后端：38 项通过，1 项先从工作区运行中排除。排除项为会创建 CSV 的 pipeline 测试；随后单独将 `CSVExporter.DATA` 指向系统临时目录运行，通过。测试使用 `.venv/bin/python -B -m pytest -q -p no:cacheprovider -k 'not test_pipeline_no_fake_speed_csv_and_bottom_center'`。未改写工作区测试输出。
- 前端：`npm --prefix frontend test`，8 项通过；`frontend/node_modules/.bin/tsc --project frontend/tsconfig.json --noEmit --incremental false` 通过。没有为评审重跑构建、真实视频 smoke 或浏览器测试；现存 `TEST_REPORT.json` 与界面记录是先前验收证据，不是本轮新执行结果。
- 依赖漏洞：`npm audit --package-lock-only --ignore-scripts` 无法连接镜像和 npm 官方 registry，均报 DNS `ENOTFOUND`。因此本报告不宣称当前依赖安全或存在已确认的高危公告。
- 文档：检查了 README、更新日志、界面/导航/计数/孪生记录以及所有本地 Markdown 链接；本地链接均存在，README 的产品边界与主要代码相符。没有发现值得单列的文档缺陷。
- 未审范围：未验证视频编码、可变帧率输入及恶意媒体解码；未运行模型、GPU、真实隧道素材、长视频压力测试或完整浏览器攻击路径；未审计 Python 全部传递依赖漏洞（当前环境网络受限）。

## 实施顺序建议

如后续进入实施，建议先建立前端交互回归覆盖（R05），再修复帧同步和编辑数据绑定（R03、R04、R08、R09）；后端先处理失效会话忙循环（R02），再加入资源和并发检查（R01、R06、R10）。之后修正逆行窗口、输入时间契约及安装/性能问题（R07、R11–R14）。R05 的组件测试为 R03、R04、R08、R09 的验收前置；R10 的请求体限制需要合成 multipart 边界测试。P3 可单独排期。

本次仅提交本报告到 improve 许可的计划目录；没有修改源代码、提交、安装或下载依赖、发布 issue。没有生成实施计划；可按 R 编号选择后续要规划的发现。
