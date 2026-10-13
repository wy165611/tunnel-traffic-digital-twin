from pathlib import Path
P=Path(__file__).resolve().parent
base=(P/'build_docx.py').read_text()
base=base.replace("('Normal',12),('Title',17),('Heading 1',12),('Heading 2',12),('Caption',10.5)","('Normal',12),('Title',18),('Heading 1',14),('Heading 2',12),('Heading 3',12),('Caption',10.5)")
base=base.replace('pf.line_spacing=1; pf.space_before=Pt(0); pf.space_after=Pt(1)','pf.line_spacing=1.15; pf.space_before=Pt(0); pf.space_after=Pt(4)')
base=base.replace('pf.space_before=Pt(3); pf.space_after=Pt(1)','pf.space_before=Pt(8); pf.space_after=Pt(4)')
# Maximize screenshot and diagram readability in the expanded edition.
for old,new in [("源码绘制',3.0)","源码绘制',3.5)"),("非实测道路',3.7)","非实测道路',3.8)"),("界面，未标定',4.5)","界面及同一ID局部放大，未标定',9.6)"),("机器过线',3.0)","机器过线',3.0)"),("非真实精度实验',3.8)","非真实精度实验',4.8)"),("真值核验',3.6)","真值核验',4.3)")]:base=base.replace(old,new)
base=base.replace('单目测速须标定尺度[2]和独立真值[3]','单目测速须可靠的场景尺度[2]和独立速度真值[3]')
base=base.replace('参考文献', '参考文献',1)

def calls(items):
 out=[]
 for item in items:
  if item[0]=='h':out.append('h('+repr(item[1])+','+str(item[2])+')')
  else:out.append('p('+','.join(repr(v) for v in item[1:])+')')
 return '\n'.join(out)+'\n'
def before(anchor,items):
 global base
 assert anchor in base,anchor
 base=base.replace(anchor,calls(items)+anchor,1)
def after_line(anchor,items):
 global base
 pos=base.index(anchor); end=base.index('\n',pos)
 base=base[:end+1]+calls(items)+base[end+1:]

before("h('1.2",[
('p','隧道空间相对封闭，车辆进入、停留与行驶方向需要结合明确道路位置判断。本作品选择视频感知作为入口，目标是把既有画面组织为可查看的车辆状态、断面统计和疑似事件证据。面对运营人员或竞赛评委，系统应回答车辆位于哪条车道、统计针对哪个时间段、报警由哪项规则产生，以及能否返回原视频核验，而不是只输出一个未经解释的数值。','docs/features-analysis.md','README.md'),
('p','从工程实现看，检测框属于图像坐标，跟踪ID属于一次分析中的关联结果，米制速度则需要道路尺度与有效时间。三者不能相互替代。同样，检测到的轨迹数、穿越计数线的次数与人工观察到的物理车辆总数也可能不同。作品把这些口径显式保存在状态和导出数据中，使使用者能够识别结果的含义与适用范围。','backend/processor.py','backend/exporter.py','docs/accuracy-evaluation.md')])
after_line("p('交通深度学习综述",[
('p','相关研究给出的测速结果建立在其自身标定、数据和独立参考测量上，不能直接移用到本项目。Sochor等建立了具有独立速度测量的单目测速数据集[3]，说明“能够显示速度”与“速度误差已经验证”是不同阶段。本作品目前完成前者所需的软件路径和未标定保护，但演示桥梁没有可靠实测尺度，因而不报告真实测速误差。','docs/accuracy-evaluation.md','backend/traffic/speed_estimator.py'),
('p','预训练模型的发布资料用于确认权重来源与可选网络，论文用于解释已有技术和评测原则。发布者在其数据集上的性能不能作为作品在桥梁或隧道上的准确率；采用YOLO11n也不表示本作品训练了YOLO11网络。本文只将与源码相符的组件、流程和已有证据写为已实现内容。','models.json','backend/vision/detector.py','docs/accuracy-evaluation.md')])
after_line("p('当前完成本机录像分析",[
('p','实现范围包括车辆检测与ID跟踪、人工道路几何配置、满足前提时的定位测速、流量和车道统计、二维同步展示、异常规则、历史报告、证据复核、机位模板及人工过线/事件评测。人工速度真值仍需独立设备或独立距离时间核验；三维场景、车辆动力学、跨镜头重识别、多摄像头并发与生产级权限管理不在当前完成范围内。','docs/features-analysis.md','docs/visual-evaluation.md','backend/service.py'),
('p','本文将四类证据分别使用：当前源码说明功能如何实现；软件测试检查契约和边界；保存的桥梁运行输出说明真实素材能够经过流程；人工真值评测才回答计数、测速或报警误差。计划文件中提出的功能若未找到对应实现与验收，不作为已完成工作；历史通过数量采用当时记录，本次回归数量另行标明。','plans/002-verification.md','plans/2026-10-02-implementation-status.md','docs/accuracy-evaluation.md')])
after_line("fig(1,",[
('p','输入层保存视频内容身份、道路配置和模型参数。分析层依次解码、执行间隔检测、更新跟踪、计算接触点，再根据观测与标定状态决定是否进行测速、计数及规则判断。输出层一方面发布完整帧快照，另一方面写入统计段与事件事实。浏览器使用相同快照展示视频与孪生；历史报告和人工评测读取已经保存的记录。','backend/processor.py','backend/service.py','backend/exporter.py'),
('p','后端采用整帧处理与导出锁，使某一帧的车辆、统计和事件来自一致处理结果。分析会话与统计段是不同对象：会话承担当前播放和处理，统计段承担有固定来源与条件的记录。更换视频、定位或调整关键条件后形成新的统计段，避免把不同时间区间或不同标定条件拼接为一组指标。','backend/processor.py','backend/service.py','docs/features-analysis.md')])
before("p('预训练权重见表2",[('h','2.2.1 检测模型来源与输入适配',3)])
after_line("['SSDLite MobileNetV3'",[
('p','默认VisDrone YOLO11n来自dronefreak发布的微调权重，适合当前俯拍小目标演示的选择依据是项目已有素材抽查，不是本地重新训练。COCO YOLO11n来自Ultralytics官方权重，可作为通用交通视角的备选；SSDLite采用Torchvision提供的COCO权重和320×320输入。三种适配器统一输出位置、类别与置信度，便于沿用后续同一跟踪与分析流程。','models.json','backend/vision/detector.py'),
('p','模型选型同时考虑视角、目标像素尺寸和本机处理成本。当前默认配置置信度阈值0.40、YOLO输入尺寸960、CPU线程数4；分块检测选项存在，但默认tiled=false，本说明书不据此宣称已验证分块检测提升。降低阈值可能增加误检，提高阈值可能漏掉小目标；调整输入尺寸会改变计算量和可见细节，最终取舍仍需同一真值区间的对照。','config.yaml','backend/vision/detector.py'),
('p','实际解码画面按最长边不超过960像素缩放供处理与编码，分析后的框和接触点按横纵缩放比恢复到原图像素。道路配置、原视频叠加与导出的像素坐标以原始尺寸为基础，避免将处理分辨率误当原视频尺寸。权重由本地文件加载并校验摘要；这个校验能核对文件一致性，不能验证模型精度。','backend/vision/video_reader.py','backend/processor.py','backend/vision/weights.py'),
('h','2.2.2 Kalman预测与轨迹关联',3)])
after_line("p('observed=true",[
('p','跟踪状态由框中心cx、cy、宽w、高h及其四个变化量组成。预测阶段按逐帧常速度模型推进，观测阶段用匹配检测框修正。状态转移中的步长按一次处理帧计算，变化量属于框几何的逐帧变化，并非米每秒；实际物理速度另外由道路点与解码时间计算。对可变帧率素材，这一区分尤为必要，不能把Kalman内部变化量直接当作真实车速。','backend/vision/tracker.py','backend/traffic/speed_estimator.py'),
('p','IoU定义为两框交集面积与并集面积之比。当前关联先排除IoU低于0.20的候选，再进行Hungarian全局分配，防止明显不相交的候选占用本可成立的匹配。未分配检测创建新ID，未关联轨迹继续预测并增加漏检年龄；默认命中至少2次才进入输出，年龄超过30帧移除。','backend/vision/tracker.py','config.yaml'),
('p','轨迹内部保留与界面输出使用不同期限。处理器还要求漏检年龄不超过min(max_age,2×检测间隔)，默认即4帧，避免把长时间没有观测的框持续展示。轨迹类别采用检测置信度约束减少低置信度抖动，但未加入外观重识别，因此类别稳定或ID连续都不是物理车辆身份正确的证明。','backend/processor.py','backend/vision/tracker.py'),
('h','2.2.3 实际观测与预测位置的使用边界',3),
('p','实际观测指本帧检测与轨迹成功关联后的滤波位置，仍会受到检测框误差影响；预测指未得到本帧观测时的状态外推。两者均可用于可视化连续性，但只有实际观测追加分析轨迹、更新过线、测速与事件规则。CSV保存observed字段，使报告能够剔除预测行，不能仅因某个预测行保留了最近速度，就将它视为新的独立测量样本。','backend/processor.py','backend/reports.py'),
('p','ID分裂可能使同一物理车辆形成两个确认轨迹；遮挡后重新出现也可能获得新ID。计数去重是“同一段同一轨迹ID一次”，不能保证“同一物理车辆一次”。因此28个确认ID不等于28辆真实车，98.9%的相邻帧ID保留率也不等于MOT准确率。物理身份正确性必须通过独立逐车或逐帧真值核验。','backend/vision/tracker.py','backend/traffic/flow_counter.py','docs/accuracy-evaluation.md')])
before("p('将轨迹框还原",[('h','2.3.1 四点道路标定与米制坐标',3)])
after_line("eq('X = '",[
('p','四个图像点对应道路平面矩形的四个角，H将齐次像素坐标映射到道路坐标；尺度由W、L确定，不由检测模型推断。检测框底边中心近似轮胎与道路的接触位置，适合解释车辆在道路上的位置，但它并非真实接触点测量。在遮挡、俯视、检测框偏移或车辆姿态变化时，该近似会带来定位和测速误差。','backend/calibration/homography.py','backend/processor.py'),
('p','程序要求角点为有限数值、构成不交叉的凸四边形，面积与矩阵满足有效性条件，并检查道路尺寸范围。通过这些检查仅表示几何计算可进行，不表示角点对应正确、道路平面成立或尺寸已经实测。前端输入和模板复制都须由操作者确认尺度来源；本作品没有利用无人机高度、焦距或平均车长自动补出真实尺寸。','backend/calibration/homography.py','docs/camera-templates.md'),
('p','车辆点位于标定多边形内才输出米制位置；离开区域时不外推为有效速度。道路坡度、拱形路面、镜头畸变及相机运动会破坏单平面固定映射。应用到隧道前应保存机位、四角实物依据、测量方法与尺寸记录，并用未参与四点设置的独立测量位置检查映射偏差；这些属于待完成的实测验证。','backend/calibration/homography.py','backend/processor.py','docs/accuracy-evaluation.md'),
('h','2.3.2 实际时间戳与窗口最小二乘测速',3)])
after_line("p('rᵢ为道路点",[
('p','窗口最小二乘以时间为自变量、二维米制位置为因变量，利用多个观测点估计速度向量，减少逐点差分对框抖动的放大。smoothing_frames=10在实现中表示最多10个实际观测点，检测间隔改变时覆盖的秒数也随之变化，并非固定10个视频帧。最少5点与0.1s跨度用于避免样本不足和时间分母过小；最近3次速度模长再求均值会降低抖动，也引入一定响应延迟。','backend/traffic/speed_estimator.py','backend/processor.py'),
('p','视频时间来自解码器提供的PTS，要求有限、非负、严格单调。当前读取器遇到不可信时间戳时明确报错，而不以处理耗时或平均FPS合成时间。录制视频定位采用原始帧序号探测实际PTS，选择第一个不早于目标时间的帧，避免可变帧率输入按平均FPS定位到错误帧。原视频帧率仍用于元数据与部分近似步进，不承担真实测速的时间分母。','backend/vision/video_reader.py','tests/test_video_timing.py'),
('p','观测间隔超过max(0.5s,2.5×检测间隔/视频FPS)时重置测速及相关规则缓存，避免跨较长遮挡直接计算速度；离开有效标定区域也会清空测速历史。当前规则在重新累积足够样本前保持不可用。未标定记录中的空值表示测量前提不成立，不能改写为0km/h，因为0代表已测得静止，会错误触发停车判断。','backend/processor.py','backend/traffic/speed_estimator.py'),
('p','导出的加速度由相邻平滑速度差除以时间差计算，单位m/s²；急减速规则另用至少0.5s的速度变化以降低单帧波动。二者计算跨度不同，报警阈值不应机械地应用到CSV逐帧加速度列。速度和加速度是否准确仍依赖标定、接触点、时间与轨迹，软件公式正确不能代替独立参考测量。','backend/traffic/speed_estimator.py','backend/events/rules.py'),
('h','2.3.3 过线计数 车道归属与时间窗口',3)])
after_line("p('过线判定检查",[
('p','计数线是有限线段。程序检查同一ID相邻观测点之间的运动线段与它相交，排除仅穿越延长线的车辆以及平行移动。首次有效穿越时记录当前视频时间、车辆类别和车道，并将该ID加入去重集合。计数时间对应首次观测到跨线的采样时刻，没有按运动速度内插到精确穿越时刻；人工评测容差应考虑采样间隔和标注误差。','backend/traffic/flow_counter.py','backend/processor.py'),
('p','车道由人工多边形定义，接触点落入哪一多边形即归属该车道；未落入已定义车道的目标保留为“未划分”，不自动补画道路或推断车道。逐帧在场类别分布与过线类别累计分布是不同统计量：前者描述当前显示轨迹，后者描述已通过断面的ID。变道时的过线类别和车道取触发时结果，人工真值应采用同一统计口径。','backend/traffic/lane_detector.py','backend/traffic/flow_counter.py','backend/traffic/traffic_metrics.py'),
('p','10/30/60s车道窗口计数按当前时刻之前的指定区间聚合过线记录，并报告窗口长度、实际覆盖秒数与是否完整。伴随窗口行保存的观测数、预测数和平均速度是当前采样时刻状态，其中均速仅取实际观测且速度有效的车辆；它不是对整个10/30/60s时间段内所有车辆求得的窗口均速。阅读CSV时必须区分“过线的时间聚合”和“采样时刻的在场状态”。','backend/processor.py','backend/traffic/flow_counter.py'),
('p','每分钟流率将最近60s内过线数按实际覆盖时间折算；未覆盖完整60s时明确标记估计。累计流量取每帧累计列的最大值，若把它逐帧相加将重复计算同一过线。平均车头时距使用首末过线时间及穿越次数，只有超过一次穿越才可计算；这些指标均描述配置断面，不能直接解释为整段隧道的容量或交通服务水平。','backend/traffic/flow_counter.py','backend/reports.py')])
after_line("p('后端整帧完成",[
('p','状态传输以一帧为单位，不分别让前端独立拉取图像和车辆坐标。后端修订号表示发布状态的更新顺序，会话标识区别不同分析对象；前端抛弃旧会话、旧修订与晚到的解码结果。图像解码存在异步完成次序，若只替换坐标而图像仍停在旧帧，即会产生视觉误差。当前成对提交机制与乱序测试针对这个问题。','backend/main.py','frontend/src/utils/snapshotState.ts','frontend/tests/snapshotState.test.mjs'),
('p','同帧同步保证已提交图像与状态对应，并不保证浏览器显示每一原视频帧。推送、JPEG解码、渲染和本机负载可能影响刷新速度；处理吞吐、视频PTS和显示帧率是三个不同量。系统将检测耗时、跟踪耗时和处理FPS用于运行状态观察，当前没有完成浏览器显示帧率或端到端时延的独立测量。','backend/processor.py','backend/main.py','frontend/src/App.tsx')])
after_line("p('未标定时保留",[
('p','二维孪生采用统一坐标映射绘制道路、车道、车辆和轨迹。未配置道路时仅显示图像范围，避免用默认车道制造场景信息；标定后使用道路米制坐标并保持比例。横向、竖向和旋转道路的朝向变换与位置变换共用几何依据，实际截图可用于检查对应关系。它是对观测状态的二维映射，不是道路三维重建、交通行为模拟或完整物理仿真。','frontend/src/utils/twinGeometry.ts','frontend/src/components/DigitalTwin.tsx','docs/twin-orientation.md'),
('p','图4来自3840×2160横向桥梁素材的实际生产界面，与图8使用的2160×3840竖向记录不是同一个运行。横向图用于方向、比例及同帧对应的功能展示，竖向CSV用于统计口径说明；本文不把不同素材的截图和数据组合为同一组实验。横向车道为人工描绘的图像轮廓，没有加入可靠实测尺度。','docs/twin-orientation.md','output/playwright/twin-horizontal.png')])
after_line("p('异常停车、急减速",[
('p','停车判断保存该ID开始低于3km/h的时刻，低速累计达到3s才产生候选，速度回升则清除计时。规则能发现“持续低速”的目标，但不能区分拥堵排队、许可停车、紧急停车或正常等待。隧道落地需要结合停车区域、运行工况及人工复核；当前没有实现停车区语义或事故因果诊断。','backend/events/rules.py'),
('p','急减速缓存速度样本，用至少0.5s跨度的速度差计算加速度，低于−4m/s²产生候选。采用较长时间差是为抑制单帧峰值，仍不能消除错误标定、遮挡后框跳动和检测接触点偏差。该规则仅识别速度变化模式，不等于碰撞预测或危险行为责任判定。','backend/events/rules.py'),
('p','逆行将短时世界轨迹位移与车道合法方向比较，方向余弦小于−0.6且速度超过3km/h时开始计时，持续至少1s才触发。默认方向可由各车道覆盖，未归属车道时使用全局方向。低速方向不稳定、车道设置错误或ID中断均可能影响判定。合法方向必须与当前标定和道路视图一致，不能从屏幕左右方向直接推断。','backend/events/rules.py','backend/processor.py','config.yaml')])
after_line("['冷却与车道窗口'",[
('p','同一ID同一事件类型默认冷却5s，满足持续条件的目标不会在每帧形成新事件，但冷却结束后仍可能再次报警。因此事件CSV的条数是规则触发次数，不是事故数，也不是异常车辆数。画面中的短时警示状态与持久保存的事件记录分别服务实时浏览和后续复核，历史事件不会因警示标记消失而删除。','backend/events/rules.py','backend/processor.py')])
after_line("fig(5,",[
('p','报警证据以事件发生时的事实为基础保存，关联统计段、事件ID、帧号、时间、车辆与规则条件。机器事件CSV、截图与事实元数据用于重现“系统当时看到了什么”；人工确认、误报判断和备注另存，回答“复核者如何解释它”。后续修改复核状态不改变机器规则曾经触发这一事实。','backend/evidence.py','backend/exporter.py'),
('p','独立回放先按统计段保存的视频ID和内容身份核验原文件，然后通过HTTP Range读取邻域。该播放器与当前分析播放器分开，查看历史事件不定位或暂停实时分析。若原视频丢失或内容改变，禁止把同名替换文件当作原来源继续回放；已保存截图和复核记录仍可查看，但不能据此作新的完整区间真值声明。','backend/evidence.py','backend/annotations.py','docs/visual-evaluation.md'),
('p','确认已报事件只能检查所见报警，发现不了系统完全没有报出的真实事件。人工评测因此提供完整录像独立查看、过线记录和未映射事件入口。报警复核与科学评测共享来源追溯思路，但数据对象和完整性声明不同，不能直接把“已确认报警数”当作TP或把未确认报警全部当作FP。','docs/visual-evaluation.md','backend/evaluation.py')])
before("p('统计段保存来源",[('h','2.6.1 历史统计段与分析报告',3)])
after_line("p('CSV及离线",[
('p','运行目录保存run.json和按用途划分的CSV。run.json记录来源身份、模型与分析配置、道路几何、标定状态、统计段起止及完成状态；traffic_statistics.csv保存逐帧整体统计，vehicles.csv保存逐车辆帧明细，events.csv保存机器事件，lane_statistics.csv保存车道采样与窗口。原始记录比趋势图更适合核查单位、样本和条件。','backend/exporter.py','backend/processor.py'),
('p','报告速度平均采用所有有效观测车辆帧，不是先对每车平均再对车辆平均，因此长时间在画面中的车辆会贡献更多样本。覆盖率反映观测样本中有多少满足测速条件；有效样本少时即使存在速度均值，也不能认为整段交通速度已经充分测量。条件对照必须保留不同参数，模型输出数量增加既可能来自漏检减少，也可能来自误检或ID分裂增加。','backend/reports.py','docs/features-analysis.md'),
('h','2.6.2 固定机位道路模板与尺度复用',3)])
after_line("p('固定机位模板保存",[
('p','模板解决相同固定机位重复描绘车道和计数线的问题。只有已经保存的道路几何进入模板，当前未提交草稿不混入模板事实；名称、备注和修订版本用于识别与冲突检查。同比例分辨率转换按坐标比例映射，在独立预览中确认后应用。默认只复制几何并清除原真实尺度，减少把另一机位测量条件无意带入当前视频的风险。','backend/camera_templates.py','docs/camera-templates.md'),
('p','受控验收检查了200×400到100×200的坐标减半、计数线y120到y60、超过1%的宽高比偏差拒绝应用，以及默认清尺度和单独确认复制已知测试尺度。这里20×40m为受控素材的已知构造条件，不是桥梁实测尺寸；它验证功能契约，不证明隧道机位或真实尺度能够自动迁移。','plans/002-verification.md','docs/camera-templates.md'),
('h','2.6.3 人工标注 版本绑定与一对一评测',3)])
after_line("p('人工核验已关闭段",[
('p','标注草稿与完整真值有不同状态。只有操作者记录核验者、区间、已完整查看的类别并确认完整性，保存版本才可正式评测；未勾选类别表示尚未知，空数组只有在该类别完整核验后才表示没有目标。当前可视化界面不核验速度，speeds=[]与speed_state=unreviewed不能解释为确认没有速度对象。','docs/visual-evaluation.md','backend/annotations.py'),
('p','标注采用独立revision和运行配置指纹。修改姓名、区间、类别或条目撤销完整声明，保存时校验expected_revision，避免另一个编辑窗口覆盖新版本；评测与下载绑定精确保存版本。恢复本机草稿需显式选择，恢复后也撤销完整声明。本机缓存帮助防丢失，不等于服务真值或跨设备备份。','backend/annotations.py','docs/visual-evaluation.md'),
('p','暂停时的ID辅助查询仅从已有CSV读取0.5s以内最近的实际观测样本，不重新运行检测。它帮助建立物理车辆与当前段ID的映射，却不能确认系统检测正确；完全没有轨迹的事件应无ID记录，并计入漏报，不能用空ID匹配任意预测。独立播放器上一/下一帧按保存FPS近似步进，浏览器与可变帧率解码不保证精确逐帧定位，评测记录以显示并保存的原视频秒数为准。','docs/visual-evaluation.md','backend/annotations.py')])
after_line("p('事件按类型",[
('p','正式评测先核对来源、配置、尺寸、区间和所评CSV的有效性，再进行计数及事件比较。区间计数由末端累计值减起点之前累计值，与人工过线条目数比较绝对误差；事件在类型、映射ID和容差共同约束下作一对一匹配，不能让一个机器报警重复匹配多个真值。输入损坏或所需CSV缺失时返回明确不可用，不把缺失文件视作零目标。','backend/evaluation.py','docs/visual-evaluation.md'),
('p','precision=TP/(TP+FP)，recall=TP/(TP+FN)。分母为零时指标不可定义，保存null或不可用；只核验计数时不计算事件指标。现有CLI还可对独立速度真值按ID和近邻实际观测时刻匹配，输出MAE、RMSE及匹配覆盖率，但当前没有可据此报告的真实测速结果。界面可完成记录和计算，不代表真值的人工完整性已经由软件自动证明。','backend/evaluation.py','docs/accuracy-evaluation.md')])
after_line("p('observed与标定",[
('p','这一设计针对“界面存在数值便被理解为测量成立”的问题。实际实现把输入尺度、区域、观测状态和最少样本作为前提，未满足前提时保留空状态，并让原始导出与界面一致。可验证特色是数据含义明确和错误前提受到约束；不将采用已有最小二乘公式或预训练模型本身列作基础算法创新。','backend/processor.py','backend/traffic/speed_estimator.py','backend/exporter.py')])
after_line("p('图像与状态成对",[
('p','同帧提交解决异步显示的工程一致性，独立回放解决历史复查与当前会话争用，不可变事实与独立复核记录解决人工判断覆盖机器历史的问题。三者形成从车辆状态到原始画面和条件记录的解释路径。已有浏览器验收观察到历史播放器定位时，后台当前分析仍继续完成；该证据支持操作隔离，不能推出端到端同步误差为零。','plans/002-verification.md','backend/evidence.py','frontend/src/utils/snapshotState.ts')])
after_line("p('模板默认清尺度",[
('p','机位模板减少重复几何输入，人工文档版本绑定防止旧结论冒充新标注。两者共同保留条件变更的可见性：几何复用仍需确认实测前提，标注变化必须重新完整核验与计算。贡献在于将复用效率与测量边界结合，并提供可追溯记录；它不是自动标定、自动生成真值或跨隧道迁移学习。','backend/camera_templates.py','backend/annotations.py','docs/visual-evaluation.md')])
after_line("p('本次环境为",[
('p','后端以Python、FastAPI、OpenCV、PyTorch、NumPy和SciPy组合完成解码、检测、跟踪与几何统计；前端以React、TypeScript、Vite和ECharts提供工作台与趋势展示。本次核验还记录OpenCV 4.13.0.92、Torchvision 0.26.0及Ultralytics 8.4.32。这些版本说明本机验证条件，不构成跨平台安装或不同硬件性能承诺。','README.md','models.json'),
('p','竖向demo.mp4为主要机器运行证据，保存内容身份3a247cda14c4bfd01d7d6a3a，与本次重新计算的SHA256前24位一致。原视频共有256帧，元数据帧率30FPS；最后解码时间为8.5s，视频时长约8.533s，二者一个表示末帧PTS，一个含最后帧持续时间，不应认为记录丢失了0.033s。该运行未加入实测尺度。','backend/data/runs/20261002-170236-c53990/run.json','backend/data/runs/20261002-170236-c53990/traffic_statistics.csv','docs/review-smoke-2026-10-02.json')])
after_line("p('使用顺序为",[
('p','导入后先检查视频比例与已保存的道路轮廓，再确定有限计数线的位置和各车道合法方向。若没有真实道路尺寸，则直接在未标定状态演示检测、轨迹、过线和同帧孪生；不要为了出现速度而填入猜测尺度。具备可靠尺度后再设置四点区域，检查样本是否处于区域内，以及速度何时达到最少观测点条件。','README.md','docs/camera-templates.md','backend/processor.py'),
('p','分析结束后以统计段查看累计值和原始CSV，人工复核报警时检查触发时刻、目标ID、规则条件和邻域原视频。建立真值时应离开机器事件列表，独立核验整个区间并记录完全漏报。完成保存版本的评测后再下载真值与结果，保持run身份、配置和revision一致，避免将不同运行的ID用于比较。','docs/features-analysis.md','docs/visual-evaluation.md')])
after_line("p('2026年10月3日",[
('p','后端回归覆盖道路几何有效性、有限计数线、测速与规则、导出报告、来源身份、模板、标注版本和评测边界；前端回归覆盖同帧状态提交、几何映射、人工输入及异步过期状态。本次测试使用隔离DATA并关闭缓存写入，未把测试尺度或构造真值写入用户历史运行目录。测试通过表示这些断言在当前环境成立，不等于真实交通场景覆盖完整。','tests/conftest.py','tests/test_analysis_features.py','tests/test_camera_templates.py','tests/test_annotations.py','frontend/tests/snapshotState.test.mjs'),
('p','运行检查启动隔离实例，核对HTTP响应、可信来源WebSocket空闲连接和正常关闭，结束后移除该实例。它验证服务基本可用与进程退出，不测实际摄像头断流重连，也不提供长时间负载或GPU性能结果。已有历史生产构建和浏览器证据与本次软件回归分别记录，本文没有重新声称完成全部历史界面流程。','scripts/check_runtime.py','plans/002-verification.md'),
('p','历史记录还覆盖独立接口22项、边界6项、320px和390px人工弹窗、草稿恢复及错误导入。部分验证使用200×400、10FPS、120帧受控素材与颜色检测器，事件标注包含刻意构造的FP和无ID FN；这类条件便于检查确定性行为，却不具有真实车辆检测和隧道异常识别的科学真值。','plans/002-verification.md')])
after_line("p('尚无已保存",[
('p','选择该段作为说明书的数据示例，是因为它保留原视频内容身份、分析配置、道路场景、标定状态和完整CSV，能够核对数字来源。较早运行和单次smoke用于说明历史进展，不混合为新的对照实验。当前没有另一个同真值、同区间并受控改变唯一条件的精度实验，也没有消融实验或提升百分比。','backend/data/runs/20261002-170236-c53990/run.json','plans/002-verification.md')])
after_line("p('该段1074条",[
('p','2162行车辆明细由1074条实际观测和1088条预测构成，同一ID可在不同帧重复出现。19次机器过线由去重后的轨迹穿越产生，28个ID为整个区间内曾输出的确认轨迹，13为某一时刻最多同时在场轨迹。三个指标的时间范围和分母不同，不存在“19/28即检测准确率”这样的换算关系。事件0条首先与未标定门槛一致，无法证明原视频完全没有异常。','backend/data/runs/20261002-170236-c53990/vehicles.csv','backend/data/runs/20261002-170236-c53990/traffic_statistics.csv','backend/data/runs/20261002-170236-c53990/events.csv'),
('p','图7受控流程输出计数绝对误差0、TP2/FP1/FN1，对应precision与recall均为66.7%。这里的标签为工作流验收而构造，且包含专门检查未映射漏报的边界条目；数字只说明一对一匹配与界面下载一致，不列为真实报警准确率。它与图8的真实桥梁CSV属于不同证据层次，也不能据此选择最佳报警阈值。','plans/002-browser-result.json','plans/002-verification.md')])
# Two additional native tables summarize real output and unfinished validation.
anchor="h('4.5 当前局限与后续验证计划')"
extra="""table(5,'真实桥梁运行结果及统计口径',['指标','实际记录','分母 条件与解释'],[
['统计区间与帧数','0.0–8.5s；256个统计帧','末帧PTS；30FPS原视频；来源身份一致'],
['确认轨迹与在场量','28个ID；最多同时13个','ID非物理车辆数；在场包含预测'],
['机器过线累计','19次','有限计数线；同ID同段去重'],
['车辆帧样本','1074观测+1088预测=2162行','重复ID跨帧计行；非2162辆车'],
['有效观测速样本','0/1074；覆盖率0%','未实测标定；均速与误差不可用'],
['机器事件与流率','0条；末帧134.12辆/min','报警门槛关闭；19÷8.5×60短时折算']],[3.8,5.5,7.7],['backend/data/runs/20261002-170236-c53990/run.json','backend/data/runs/20261002-170236-c53990/traffic_statistics.csv','backend/data/runs/20261002-170236-c53990/vehicles.csv','backend/data/runs/20261002-170236-c53990/events.csv'])
"""
assert anchor in base;base=base.replace(anchor,extra+anchor,1)
after_line("p('现有桥梁录像",[
('p','后续应先建立来源合法、场景可说明的连续视频集合，分开记录隧道入口与内部、明暗变化、遮挡和车流条件；保存机位、录像时段、文件身份及相机是否移动。建议由两名标注者独立核验并复查分歧，完整记录区间端点、物理车辆、系统ID映射、事件定义和容差。不以挑选少数效果良好片段代替整体报告。','docs/accuracy-evaluation.md'),
('p','计数实验应在同一来源、计数线和完整区间内比较机器计数与人工过线次数，报告分场景绝对误差，并解释ID分裂、有限线段漏穿越和端点采样误差。异常实验应明确首次满足规则的时刻和冷却口径，分别报告三类事件TP、FP、FN及分母；没有真实目标的类别报告样本缺失或不可定义，不制造高召回率。','docs/accuracy-evaluation.md','docs/visual-evaluation.md'),
('p','测速实验须取得独立参考速度，建立参考设备或人工距离时间记录与视频PTS、物理车辆、系统ID的对应。先报告有多少真值样本成功匹配，再给MAE和RMSE：只对成功测得样本平均会掩盖无输出和漏检。道路四点和参考测速不能都来源于系统自身，否则形成自我验证。真实测试规模应由取得的材料决定，本文不预填样本量或目标误差。','docs/accuracy-evaluation.md'),
('p','软件层面还需验证长时写入、视频来源缺失、磁盘空间不足、RTSP断流恢复、不同硬件推理和干净安装。新增实时流入口必须同时验收有效时间、失败状态与恢复行为；当前底层VideoCapture支持流字符串不等于产品已具备完整接入能力。多摄像头扩展也需重构单分析会话的资源管理与隔离，不能简单增加一个下拉选项即称已完成。','backend/vision/video_reader.py','backend/service.py','plans/2026-10-02-implementation-status.md')])
anchor="h('5 应用前景与推广条件',1)"
extra="""table(6,'已完成工作与待验证事项',['领域','已完成及证据','待补材料或验收'],[
['检测与跟踪','预训练适配、Kalman/IoU；测试与真实smoke','逐帧框与物理ID真值；mAP/MOT评测'],
['道路测量','四点计算、时间拟合、未标定留空','机位与尺寸实测；独立参考速度'],
['统计与事件','有限线段、窗口、规则、证据保存','真实完整过线及三类事件标签'],
['二维展示与复核','同帧提交、回放、模板、版本评测','代表性隧道场景与机位复用验证'],
['运行与推广','本机CPU、单会话、HTTP/WS检查','RTSP、长时、GPU、安装与容量验证']],[3.4,6.7,6.9],['docs/accuracy-evaluation.md','docs/visual-evaluation.md','plans/002-verification.md','plans/2026-10-02-implementation-status.md'])
"""
assert anchor in base;base=base.replace(anchor,extra+anchor,1)
after_line("p('系统可用于监测教学",[
('p','近期可应用于教学演示与离线分析：学生或评委从原视频观察车辆，理解检测、跟踪、标定、时间拟合和统计之间的关系，并通过导出和独立回放复核结论。当前成果适合解释算法与系统协同的实现，应用价值首先来自可理解、可检查的记录链，而不是未经验证的检测精度或自动执法能力。','README.md','docs/features-analysis.md'),
('p','推广到固定隧道机位时，应先完成场景验证与尺度确认，再设置车道、方向、统计断面和报警阈值。机位模板可减少同机位重复配置，条件对照可辅助观察模型或参数输出变化，人工评测可检查真实错误。三者只有在来源与真值可靠时，才能支持后续选型；目前不能承诺阈值无需调整或不同隧道直接复用。','docs/camera-templates.md','docs/accuracy-evaluation.md'),
('p','生产使用还涉及授权、模型许可、隐私与数据保留、事件处置责任和服务可靠性。本文只提出这些推广条件，不编写尚未发生的合作、部署、经济收益或落地案例。最终竞赛提交前还应由团队核实人员信息、素材和权重使用条件、赛事实际模板及真实性声明；本文不沿用参考作品人员，也不代签承诺书。','models.json','plans/2026-10-02-implementation-status.md')])
# Avoid isolated citations at the beginning of a line.
base=base.replace("run=pa.add_run(part)\n        if re.fullmatch", "run=pa.add_run(('\\u2060'+part) if re.fullmatch(r'\\[\\d+(?:[-,]\\d+)*\\]',part) else part)\n        if re.fullmatch")
(P/'build_expanded_docx.py').write_text(base)
print('Expanded builder generated')
