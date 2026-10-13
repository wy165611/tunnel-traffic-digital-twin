# 人工真值评估流程

本项目不自动生成真值。桥梁演示素材、合成轨迹和 smoke 运行只能验证功能；不能据此给出隧道检测精度、测速误差或报警误报率。

## 数据准备

1. 取得经授权的固定机位真实视频，覆盖隧道入口/内部、日夜、遮挡和不同车流。保存来源、授权、拍摄条件、相机运动情况和文件哈希。不同场景分别报告，避免仅挑效果好的画面。
2. 计数线由人工确认；测速用实测道路平面尺寸，保留测量依据。速度真值应来自可追溯的独立设备或独立人工距离/时间核验，不能直接复制系统导出值。
3. 对每段连续完整区间逐车标注穿越；对报警明确标注事件定义、首次满足规则的时间和对应车辆。建议两人独立标注并复核分歧。
4. 导出或离线生成统计段，保留三个 CSV 和同目录的 `run.json`。真值中的 `vehicle_id` 对应这个统计段的导出 ID；人工物理车辆 ID 与系统轨迹 ID 的映射应单独保留。重跑后须重新检查映射。

## 真值文件

复制 `examples/evaluation_truth.template.json` 到自己的文件。模板 `verified=false`，工具会拒绝直接评估。实际核验完成后填写 `annotator`、`verified=true`、`video_identity` 和 `interval`。区间必须完整落在 CSV 统计时间范围内，建议选取 CSV 中已有帧的起止时间。

三个数组都必须存在。空数组表示**已完整核验该区间没有对应目标**，不能用来表示尚未标注。填写格式如下（仅说明字段，不提供虚构测量值）：

- `crossings`：每次人工核验的真实穿越一条记录，字段 `timestamp`（视频秒）。同一物理车辆来回穿越时要按系统“同一 ID 仅计一次”的口径准备对应对照，并另记 ID 切换造成的偏差。
- `speeds`：`timestamp`、`vehicle_id`、`speed_kmh`。仅用于已经实测标定的速度对照。
- `events`：`timestamp`、`vehicle_id`、`event`；类型为 `ABNORMAL STOP` / `HARD BRAKING` / `WRONG WAY`。按首次触发时间/冷却后的事件计数口径标注，不按每个报警画面重复标注。

运行：

```bash
.venv/bin/python scripts/evaluate.py \
  --run backend/data/runs/<run_id> \
  --truth /absolute/path/verified-truth.json \
  --tolerance 0.15 \
  --output /absolute/path/evaluation.json
```

工具核对视频内容哈希、真值声明、有限数值和区间。比较区间内累计流量差，输出计数绝对误差；速度按相同 ID、最近实际观测帧及时间容差匹配，输出覆盖率、MAE、RMSE（km/h）。预测位置、未标定或匹配不到的速度不会填零，也不参与误差平均；必须连同覆盖率解释结果。区间端点按导出帧时间计数，跨端点的穿越需人工复查。

报警按类型、ID、时间容差做最大数量的一对一匹配，输出 TP、FP、FN、precision、recall。冷却内反复报警不会重复匹配同一真值。无预测时 precision 为 `null`；无真值目标时 recall 为 `null`。使用者负责确认“verified”声明的真实性，工具无法证明标注正确。

## 尚需真实数据完成的评测

当前 CSV 没有导出逐帧检测框及完整检测类别匹配结果，因此这个入口不计算检测 mAP/PR、MOT ID-switch 或跨镜头跟踪精度。开展这些评测须另建逐帧框/物理 ID 标注与检测结果导出，再使用相应评测协议。当前没有真实道路测量、隧道人工真值或 NVIDIA GPU 测试，不能给这些项目填写数值结论。
