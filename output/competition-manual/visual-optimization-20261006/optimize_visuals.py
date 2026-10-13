from pathlib import Path
import shutil, json, hashlib, csv, math
from PIL import Image, ImageDraw, ImageFont

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
OLD=OUT.parent/'revision-undergraduate'
AS=OUT/'assets'; AS.mkdir(parents=True,exist_ok=True)
EV=OUT/'evidence'; EV.mkdir(exist_ok=True)
for name in ['source_manifest.json','run-summary.json','references.json','consistency_manifest.json','reporting_coverage.json','validation-20261003.json','environment.json']:
    shutil.copy2(OLD/'evidence'/name,EV/name)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((EV/'source_manifest.json').read_text())
drift=[]
for s in manifest['sources']:
    if not s.get('sha256'):continue
    p=Path(s['path']);p=p if p.is_absolute() else ROOT/p
    if p.is_file():
        now=sha(p)
        if now!=s['sha256']:
            drift.append({'path':s['path'],'previous_sha256':s['sha256'],'current_sha256':now})
            s['previous_revision_sha256']=s['sha256'];s['sha256']=now
            s['assistant_inspected_on']='2026-10-06'
for path in ['docs/linear-design/README.md','docs/linear-design/desktop-full.jpg','docs/linear-design/desktop.jpg','docs/linear-design/mobile-report.jpg']:
    if path not in {s['path'] for s in manifest['sources']}:
        manifest['sources'].append({'evidence_id':f"E{len(manifest['sources'])+1:03d}",'path':path,'sha256':sha(ROOT/path),'assistant_inspected_on':'2026-10-06','human_verification':'pending','verification':{'source_opened':True,'status':'unverified','verified_by':'','verified_on':''}})
(EV/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
(EV/'input-baseline.json').write_text(json.dumps({'captured_on':'2026-10-06','preexisting_changes_since_prior_revision':drift,'previous_docx_sha256':sha(OLD/'基于视频感知的隧道交通数字孪生系统作品说明书.docx')},ensure_ascii=False,indent=2))

FONT='/System/Library/Fonts/Hiragino Sans GB.ttc'
BLUE='#183E59';TEAL='#187B79';AMBER='#A96725';INK='#233B48';GRAY='#59717E';LIGHT='#EDF4F7'
def font(size):return ImageFont.truetype(FONT,size)
def canvas(height):
    im=Image.new('RGB',(2200,height),'white');return im,ImageDraw.Draw(im)
def text(d,xy,s,size=44,color=INK,anchor=None):d.text(xy,s,font=font(size),fill=color,anchor=anchor)
def box(d,xy,title,lines,accent=BLUE):
    x,y,x2,y2=xy;d.rounded_rectangle(xy,radius=20,fill=LIGHT,outline='#B5C6CF',width=3)
    d.rounded_rectangle((x,y,x2,y+78),radius=20,fill=accent)
    d.rectangle((x,y+40,x2,y+78),fill=accent)
    text(d,((x+x2)/2,y+38),title,46,'white','mm')
    for i,line in enumerate(lines):text(d,((x+x2)/2,y+116+i*60),line,42,INK,'mm')
def arrow(d,a,b,color=GRAY,width=7):
    d.line([a,b],fill=color,width=width);ang=math.atan2(b[1]-a[1],b[0]-a[0]);l=23
    d.polygon([b,(b[0]-l*math.cos(ang-.45),b[1]-l*math.sin(ang-.45)),(b[0]-l*math.cos(ang+.45),b[1]-l*math.sin(ang+.45))],fill=color)
def save(im,name):im.save(AS/name,dpi=(330,330))

# Figure 1 explains why this project exists rather than an algorithm pipeline.
im,d=canvas(400)
box(d,(30,45,485,335),'原始视频',['车辆与现场细节','需要连续观察'])
box(d,(605,45,1060,335),'状态表达',['位置、车道与轨迹','原视频同帧对照'],TEAL)
box(d,(1180,45,1635,335),'统计与提示',['明确区间和前提','保存系统输出'],BLUE)
box(d,(1755,45,2170,335),'回到证据',['回放与人工核查','形成研究记录'],AMBER)
for a,b in [(485,605),(1060,1180),(1635,1755)]:arrow(d,(a+10,192),(b-10,192))
save(im,'fig1-needs.png')

im,d=canvas(510)
box(d,(30,30,580,250),'输入与配置',['录像与实际时间戳','预训练模型、道路配置'])
box(d,(750,30,1360,250),'后端分析 · FastAPI',['检测、关联、道路与规则','同帧图像、车辆与统计'],TEAL)
box(d,(1630,30,2170,250),'前端工作台 · React',['视频与二维孪生','轨迹、车道、事件和图表'])
arrow(d,(590,155),(740,155));arrow(d,(1370,155),(1620,155))
text(d,(1495,105),'快照',42,GRAY,'mm');text(d,(1495,214),'WebSocket',42,GRAY,'mm')
box(d,(750,310,1360,485),'记录与证据',['来源、配置、CSV、截图'],BLUE)
box(d,(1630,310,2170,485),'历史与人工研究',['报告、回放、模板与评测'],AMBER)
arrow(d,(1055,260),(1055,300));arrow(d,(1900,260),(1900,300))
arrow(d,(1370,415),(1620,415));text(d,(1495,360),'HTTP',42,GRAY,'mm')
text(d,(305,370),'当前范围',44,BLUE,'mm');text(d,(305,440),'本机 · 单分析会话 · 二维',38,INK,'mm')
save(im,'fig2-architecture.png')

# These are literal crops from an actual screenshot; no synthetic traffic is added.
src=Image.open(ROOT/'docs/linear-design/desktop-full.jpg')
im,d=canvas(1640)
text(d,(555,47),'A 原视频检测与轨迹',50,BLUE,'mm')
text(d,(1635,47),'B 二维道路状态',50,BLUE,'mm')
left=src.crop((389,542,700,990));right=src.crop((1015,542,1235,990))
for crop,x in [(left,205),(right,1390)]:
    targeth=1000;targetw=round(crop.width*targeth/crop.height)
    crop=crop.resize((targetw,targeth),Image.Resampling.LANCZOS)
    im.paste(crop,(x,102));d.rectangle((x,102,x+targetw,1102),outline='#B5C6CF',width=3)
text(d,(555,1160),'A 局部放大 · ID 22',42,BLUE,'mm')
text(d,(1635,1160),'B 局部放大 · ID 22',42,BLUE,'mm')
for rect,x in [((521,561,668,639),255),((1090,605,1237,683),1335)]:
    inset=src.crop(rect).resize((600,318),Image.Resampling.LANCZOS)
    im.paste(inset,(x,1202));d.rectangle((x,1202,x+600,1520),outline='#B5C6CF',width=3)
text(d,(1100,1590),'原截图裁切与放大；同帧状态可核对，当前未启用真实尺度',42,INK,'mm')
save(im,'fig3-twin.png')

im,d=canvas(420)
stages=[('规则提示',['实测尺度与观测成立','保存触发条件']),('证据归档',['时刻、轨迹与截图','保留机器事实']),('独立回放',['核对原视频身份','查看提示前后']),('人工判断',['确认或否定与理由','复核记录单独保存'])]
for i,(title,ls) in enumerate(stages):
    x=30+i*550;box(d,(x,45,x+490,360),title,ls,BLUE if i<2 else (TEAL if i==2 else AMBER))
    if i<3:arrow(d,(x+500,200),(x+540,200))
save(im,'fig4-evidence.png')

im,d=canvas(520)
for i,(title,ls,color) in enumerate([
    ('同帧对应',['原画面与道路状态','理解系统在看什么'],BLUE),
    ('测量约束',['观测与尺度前提','说明哪些结果可用'],TEAL),
    ('证据与版本',['来源、配置与标注','检查结论怎样形成'],AMBER)]):
    x=50+i*735;box(d,(x,40,x+630,300),title,ls,color)
    arrow(d,(x+315,310),(x+315,382))
d.rounded_rectangle((50,390,2150,485),radius=20,fill=LIGHT,outline='#B5C6CF',width=3)
text(d,(1100,437),'共同支撑可解释、可复查、可重复的本科科研原型',46,BLUE,'mm')
save(im,'fig5-design.png')

im,d=canvas(1120)
text(d,(55,55),'A 真实桥梁历史报告 · 统计区间与机器计数',43,BLUE)
crop=Image.open(ROOT/'plans/features-report-desktop.jpg').crop((180,249,797,355))
crop=crop.resize((2100,round(crop.height*2100/crop.width)),Image.Resampling.LANCZOS);im.paste(crop,(50,135))
text(d,(55,535),'B 人工评测流程验收 · 刻意构造的标签',43,BLUE)
crop=Image.open(ROOT/'plans/002-evaluation-result.jpg').crop((325,548,1000,697))
crop=crop.resize((2100,round(crop.height*2100/crop.width)),Image.Resampling.LANCZOS);im.paste(crop,(50,615))
save(im,'fig6-verification.png')

# Standard plotting, all 256 traceable rows, no smoothing, separate statistical grains.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
fp=FontProperties(fname=FONT)
rows=list(csv.DictReader((ROOT/'backend/data/runs/20261002-170236-c53990/traffic_statistics.csv').open(encoding='utf-8-sig')))
x=[float(r['timestamp']) for r in rows]; crossing=[int(r['flow']) for r in rows]; active=[int(r['vehicle_count']) for r in rows]
fig,axs=plt.subplots(1,2,figsize=(7.2,2.65),dpi=330)
for ax,ys,color,title,ylabel,style in [(axs[0],crossing,BLUE,'A 累计机器过线','次数 / 次','-'),(axs[1],active,TEAL,'B 同时在场轨迹（含预测）','轨迹数 / 个','--')]:
    ax.step(x,ys,where='post',color=color,linewidth=1.7,linestyle=style)
    ax.set_title(title,fontproperties=fp,fontsize=10,pad=10)
    ax.set_xlabel('视频时间 / s',fontproperties=fp,fontsize=9)
    ax.set_ylabel(ylabel,fontproperties=fp,fontsize=9)
    ax.set_xlim(0,8.5);ax.set_xticks([0,2,4,6,8.5]);ax.tick_params(labelsize=8)
    ax.grid(axis='y',color='#D9E1E6',linewidth=.5);ax.spines[['top','right']].set_visible(False)
axs[0].set_ylim(0,21);axs[0].set_yticks([0,5,10,15,19]);axs[1].set_ylim(0,15);axs[1].set_yticks([0,4,8,13])
axs[0].annotate('19',xy=(8.5,19),xytext=(-19,7),textcoords='offset points',fontsize=9,color=BLUE)
fig.tight_layout(pad=.9,w_pad=1.6);fig.savefig(AS/'fig7-traffic.png',facecolor='white');plt.close(fig)

im,d=canvas(430)
stages=[('当前原型',['本机录像研究与教学','已有功能和运行材料'],TEAL),('真实隧道评测',['固定机位、尺度与真值','材料与实测结果待补'],BLUE),('实时流研究',['接入、时间与断流恢复','验收未完成'],AMBER),('扩大现场应用',['并发、权限与长时运行','建设与验证均待推进'],AMBER)]
for i,(title,ls,color) in enumerate(stages):
    x=30+i*550;box(d,(x,40,x+490,350),title,ls,color)
    if i<3:arrow(d,(x+500,193),(x+540,193))
text(d,(1100,397),'后续阶段需以前一阶段证据为依据，不设虚构时间表或部署结论',39,INK,'mm')
save(im,'fig8-roadmap.png')

s=(OLD/'build_revision.py').read_text()
s=s.replace("('Heading 1',14),('Heading 2',12)","('Heading 1',15),('Heading 2',12.5)")
s=s.replace('pf.line_spacing=1.15','pf.line_spacing=1.18')
s=s.replace("pa=doc.add_paragraph()\n    add_cited_text(pa,text)","pa=doc.add_paragraph()\n    if pa._p.getprevious() is not None and pa._p.getprevious().tag==qn('w:tbl'):pa.paragraph_format.space_before=Pt(6)\n    add_cited_text(pa,text)")
s=s.replace("    record(text,paths)\n    if text.startswith", "    record(text,paths)\n    if text.startswith(('本作品以异常停车','本作品的特色来自交通需求')):pa.paragraph_format.keep_together=True\n    if text.startswith")
s=s.replace("'assistant_checked_on':'2026-10-03'","'assistant_checked_on':'2026-10-06'")
s=s.replace("e.set(qn('w:w'),'65')","e.set(qn('w:w'),'100')")
s=s.replace("if ri==0:\n                sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E8EFF3');tcpr.append(sh)","sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'183E59' if ri==0 else ('F1F6F8' if ri%2==0 else 'FFFFFF'));tcpr.append(sh)")
s=s.replace('pa.paragraph_format.line_spacing=1\n','pa.paragraph_format.line_spacing=1.08\n')
s=s.replace("                if n==1 and ri<len(tb.rows)-1:pa.paragraph_format.keep_with_next=True\n",'')
s=s.replace('r.font.size=Pt(10.5)\n                    r.bold=ri==0','r.font.size=Pt(11)\n                    r.bold=ri==0\n                    r.font.color.rgb=RGBColor(255,255,255) if ri==0 else RGBColor(0,0,0)')
s=s.replace("if ci==0:pa.alignment=WD_ALIGN_PARAGRAPH.CENTER","if ci==0 or ri==0 or (n==5 and ci==1):pa.alignment=WD_ALIGN_PARAGRAPH.CENTER")
s=s.replace("                raw=pa.text", "                if ri==0:pa.paragraph_format.keep_with_next=True\n                raw=pa.text")
s=s.replace("表1将这些需求对应到当前功能，便于说明每个模块为何需要建设。","图1先概括从视频观察到形成可复查记录的需求关系，表1进一步对应到当前功能，说明每个模块为何需要建设。")
needle="table(1,'使用需求与作品功能的对应关系'"
s=s.replace(needle,"fig(1,'fig1-needs.png','作品要解决的观察与研究需求  根据项目需求绘制',3.1)\n"+needle)
s=s.replace('图1按照当前源码绘制','图2按照当前源码绘制')
s=s.replace('系统由视频感知、道路与交通分析、二维工作台、历史与证据管理四部分组成。后端负责读取视频、识别与关联车辆、形成统计和保存记录，前端负责道路配置、同帧展示和人工操作。图2按照当前源码绘制，体现模块之间的实际联系；它不代表已部署的多摄像头平台。','系统由视频感知、道路与交通分析、二维工作台以及历史与证据管理四部分组成。后端分析并保存记录，前端负责配置、展示和人工操作。图2依据源码绘制，表示当前本机单分析会话的联系。')
s=s.replace("fig(1,'fig1-architecture.png','系统总体架构  依据当前源码绘制',3.5)","fig(2,'fig2-architecture.png','本机系统架构与数据联系  依据当前源码绘制',4.9)")
s=s.replace('图2概括这一工作流程。','这一过程把即时观察与后续核查联系起来。')
s=s.replace("fig(2,'fig2-pipeline.png','作品使用与研究验证流程  根据已实现功能绘制',4.3)\n",'')
s=s.replace('图3解释这一关系：像素坐标表示画面位置，米制坐标还需要可靠实测尺度。示意图中的道路形状只用于说明方法，并非实际桥梁测量结果。','像素坐标表示画面位置，米制坐标还需要可靠实测尺度。道路映射本身不能证明尺寸已经实测。')
s=s.replace("fig(3,'fig3-calibration.png','道路位置映射的含义  概念示意，尺寸须独立实测',3.8)\n",'')
s=s.replace('图4展示真实桥梁画面与二维孪生的对应关系，并放大同一轨迹ID以便打印核对。','图3使用后续浅色界面验收的真实截图，分别放大原视频与二维道路视图，可核对同帧ID 22—29。')
s=s.replace("fig(4,'fig4-twin.png','桥梁视频与二维孪生同帧对照  实际界面及同一ID放大，未标定',9.6)","fig(3,'fig3-twin.png','真实桥梁视频与二维孪生  同帧截图及ID 22放大，未标定',12.7)")
s=s.replace('图4采用横向桥梁素材，与后文交通曲线使用的竖向演示录像属于不同来源，不能把两者视作同一次分析结果。','图3使用竖向桥梁演示素材，来自2026年10月3日后续界面验收；它与后文CSV示例属于不同分析会话，不能仅凭相似指标认定是同一统计段。')
s=s.replace("'docs/twin-orientation.md','output/playwright/twin-horizontal.png')","'docs/twin-orientation.md','docs/linear-design/desktop-full.jpg','docs/linear-design/README.md')")
s=s.replace("fig(5,'fig5-evidence.png','异常提示到证据复核的流程  依据当前实现绘制',2.2)","fig(4,'fig4-evidence.png','疑似事件的证据保存与人工判断  依据当前实现绘制',3.25)")
s=s.replace('图5展示从提示到解释的路径','图4展示从提示到解释的路径')
s=s.replace('图6为桥梁运行的实际报告指标区，展示了区间和累计机器计数。','报告界面示例见第4.2节图6A，用于核对统计区间和累计机器计数。')
s=s.replace("fig(6,'fig6-report.png','历史报告的区间与计数指标  实际界面，19次机器过线',3.0)\n",'')
needle="h('3.2 从双视图展示形成可解释的交通观察')"
s=s.replace(needle,"p('图5说明这些特色怎样共同支撑研究：同帧对应帮助解释状态，测量约束明确数据可用前提，证据与版本保存结论形成条件。三个方面共同服务于复查和重复研究，图中关系是对已实现设计的归纳，不代表已证明用户效率或真实交通精度提升。','frontend/src/utils/snapshotState.ts','backend/processor.py','backend/evidence.py','backend/annotations.py')\nfig(5,'fig5-design.png','作品特色之间的联系  源码与功能归纳图',4.05)\n"+needle)
needle="h('4.3 真实桥梁录像的描述性结果')"
s=s.replace(needle,"p('后续浅色界面验收记录保存了桌面、平板、手机和窄屏的实际截图，前端31项测试及生产构建通过。这是2026年10月3日后续记录，不是本次重新运行结果。图6将实际历史报告与受控评测分为A、B两个面板；二者的材料与用途不同，不能组合成一次真实精度实验。','docs/linear-design/README.md','plans/features-report-desktop.jpg','plans/002-evaluation-result.jpg')\nfig(6,'fig6-verification.png','功能验证界面  A实际桥梁历史报告  B构造标签人工评测',8.8)\n"+needle)
s=s.replace("fig(7,'fig8-traffic.png','真实桥梁运行的交通曲线  来自全部CSV统计帧，未经人工真值核验',4.3)","fig(7,'fig7-traffic.png','真实CSV曲线  累计机器过线与在场轨迹，全部256帧',6.2)")
s=s.replace('图8来自受控流程验收。','图6B来自受控流程验收。')
s=s.replace("fig(8,'fig7-evaluation.png','人工评测的保存与结果展示  受控验收，非真实交通精度实验',4.5)\n",'')
s=s.replace('表6区分当前阶段和后续阶段','图8展示各阶段之间的条件关系，表6区分当前阶段和后续阶段')
s=s.replace('项目后续宜按材料和验证条件推进，先把本机录像分析做成可重复的研究过程，再进入固定隧道机位评测，最后根据实际结果决定是否扩展实时流与多摄像头。图8展示各阶段之间的条件关系，表6区分当前阶段和后续阶段，以避免功能规划被误读为已完成成果。','项目后续应先把本机录像分析做成可重复研究，再进入固定隧道机位评测，依据结果决定是否扩展实时流与多摄像头。图8展示阶段条件关系，表6列出方向与完成状态，后续阶段均有待取得材料和验收。')
needle="table(6,'应用阶段与推广条件'"
s=s.replace(needle,"fig(8,'fig8-roadmap.png','由研究原型走向应用的条件路线  后续阶段尚待验证',3.35)\n"+needle)
(OUT/'build_revision.py').write_text(s)
print('Prepared eight figures, native-table styling, and updated provenance baseline. Preexisting drift:',len(drift))
