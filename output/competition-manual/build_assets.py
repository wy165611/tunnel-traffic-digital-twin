from pathlib import Path
import csv, json, hashlib, math
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
A = OUT / 'assets'
A.mkdir(exist_ok=True)
FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'
INK = '#172d3a'; BLUE = '#245c79'; FILL = '#edf4f7'; GRAY = '#51616a'
def font(n=38): return ImageFont.truetype(FONT,n)
def canvas(h):
    im=Image.new('RGB',(1800,h),'white'); return im,ImageDraw.Draw(im)
def txt(d,xy,s,n=38,fill=INK,anchor=None): d.text(xy,s,font=font(n),fill=fill,anchor=anchor)
def box(d,xy,s,n=38):
    d.rounded_rectangle(xy,18,fill=FILL,outline=BLUE,width=3)
    x1,y1,x2,y2=xy
    lines=s.split('\n'); dy=n*1.35
    for i,line in enumerate(lines): txt(d,((x1+x2)/2,(y1+y2)/2+(i-(len(lines)-1)/2)*dy),line,n,anchor='mm')
def arrow(d,a,b):
    d.line([a,b],fill=BLUE,width=5); ang=math.atan2(b[1]-a[1],b[0]-a[0]); r=18
    d.polygon([b,(b[0]-r*math.cos(ang-.45),b[1]-r*math.sin(ang-.45)),(b[0]-r*math.cos(ang+.45),b[1]-r*math.sin(ang+.45))],fill=BLUE)
def save(im,name): im.save(A/name,dpi=(300,300))

# Architecture: source-derived topology, not a deployed multi-camera network.
im,d=canvas(350)
for xy,s in [((20,30,330,150),'视频与道路配置\n权重摘要校验'),((405,30,805,150),'FastAPI 单会话\n解码 / 感知 / 分析'),((880,30,1250,150),'WebSocket 同帧快照\n图像 / 状态 / 统计'),((1325,30,1780,150),'React 二维工作台\n视频 / 孪生 / 明细')]: box(d,xy,s,34)
for a,b in [((330,90),(405,90)),((805,90),(880,90)),((1250,90),(1325,90))]: arrow(d,a,b)
box(d,(405,215,1250,325),'统计段归档  CSV + run.json + 截图事实\n报告 / 来源核验回放 / 独立复核 / 版本化人工评测',34)
arrow(d,(605,150),(605,215)); arrow(d,(1550,150),(1550,270)); arrow(d,(1550,270),(1250,270))
save(im,'fig1-architecture.png')

im,d=canvas(285)
labels=['解码帧 + PTS','间隔检测','Kalman + IoU','底边中心定位','观测门控','统计与归档']
for i,s in enumerate(labels):
    x=15+i*300; box(d,(x,20,x+270,105),s,34)
    if i<5: arrow(d,(x+270,62),(x+300,62))
box(d,(15,175,550,260),'预测位置 → 仅展示连续轨迹',34)
box(d,(610,175,1190,260),'有效标定 → 米坐标 / 测速 / 规则',34)
box(d,(1250,175,1785,260),'同帧图像与状态 → 双视图提交',34)
arrow(d,(750,105),(280,175)); arrow(d,(1350,105),(900,175)); arrow(d,(1660,105),(1520,175))
save(im,'fig2-pipeline.png')

im,d=canvas(400)
pts=[(110,75),(550,35),(680,310),(40,310)]
d.polygon(pts,fill=FILL,outline=BLUE,width=4)
for i,p in enumerate(pts):
    d.ellipse((p[0]-8,p[1]-8,p[0]+8,p[1]+8),fill=BLUE)
    txt(d,(p[0]+12,p[1]-34),'P'+str(i+1),32)
d.rectangle((320,150,420,215),outline=GRAY,width=4)
d.ellipse((362,207,378,223),fill='#ba5a28'); txt(d,(280,237),'检测框底边中心 (u, v)',30)
txt(d,(350,366),'原图像素平面',34,anchor='mm')
arrow(d,(740,185),(970,185)); txt(d,(855,122),'四点 H',38,anchor='mm')
d.rectangle((1050,45,1630,310),fill=FILL,outline=BLUE,width=4)
for p,s in [((1050,45),'(0, 0)'),((1550,45),'(W, 0)'),((1510,325),'(W, L)'),((1010,325),'(0, L)')]: txt(d,p,s,30)
d.ellipse((1290,178,1306,194),fill='#ba5a28'); txt(d,(1315,170),'(X, Y)',32)
txt(d,(1340,366),'道路米制平面  W、L 须实测',34,anchor='mm')
save(im,'fig3-calibration.png')

# Crops retain the original pixels; only margins/unrelated controls removed.
im=Image.open(ROOT/'output/playwright/twin-horizontal.png').convert('RGB')
crop=im.crop((0,118,1288,476))
plate=Image.new('RGB',(1288,415),'white'); plate.paste(crop,(0,50)); d=ImageDraw.Draw(plate)
txt(d,(315,24),'实际视频检测视图',30,anchor='mm'); txt(d,(960,24),'同帧二维孪生视图',30,anchor='mm')
save(plate,'fig4-twin.png')

im,d=canvas(240)
for i,s in enumerate(['观测轨迹触发规则','原子保存截图与事实','核验来源独立回放','人工判断与备注']):
    x=15+i*450; box(d,(x,20,x+420,105),s,34)
    if i<3: arrow(d,(x+420,62),(x+450,62))
txt(d,(900,160),'机器事件 CSV 与不可变截图保留；人工记录另存 reviews.json',34,anchor='mm')
txt(d,(900,210),'复核不调用实时定位；确认报警不等于完整区间真值',32,fill=GRAY,anchor='mm')
save(im,'fig5-evidence.png')

im=Image.open(ROOT/'plans/features-report-desktop.jpg').convert('RGB')
# Report facts and curves, not the unused dialog margin.
save(im.crop((180,249,797,355)),'fig6-report.png')
im=Image.open(ROOT/'plans/002-evaluation-result.jpg').convert('RGB')
crop=im.crop((325,548,1000,700))
plate=Image.new('RGB',(675,197),'white'); plate.paste(crop,(0,45)); d=ImageDraw.Draw(plate)
txt(d,(337,22),'受控流程验收  含构造标签',25,anchor='mm')
save(plate,'fig7-evaluation.png')

RUN=ROOT/'backend/data/runs/20261002-170236-c53990'
rows=list(csv.DictReader((RUN/'traffic_statistics.csv').open(encoding='utf-8-sig')))
vehicles=list(csv.DictReader((RUN/'vehicles.csv').open(encoding='utf-8-sig')))
im,d=canvas(425)
left,right,top,bottom=125,1750,65,335
for val in [0,5,10,15,20]:
    y=bottom-val/20*(bottom-top); d.line((left,y,right,y),fill='#dde4e8',width=2); txt(d,(left-25,y),str(val),30,anchor='rm')
d.line((left,top,left,bottom,right,bottom),fill=INK,width=3)
for val in range(9):
    x=left+val/8.5*(right-left); txt(d,(x,bottom+25),str(val),30,anchor='mm')
txt(d,(125,25),'数量 / 辆',32); txt(d,(950,394),'视频时间 / s',32,anchor='mm')
def path(field,color,width):
    pp=[(left+float(r['timestamp'])/8.5*(right-left),bottom-float(r[field])/20*(bottom-top)) for r in rows]
    d.line(pp,fill=color,width=width)
path('flow',BLUE,5); path('vehicle_count','#b5612d',4)
for x,color,s in [(540,BLUE,'累计机器过线'),(980,'#b5612d','在场轨迹数（含预测）')]:
    d.line((x,26,x+70,26),fill=color,width=5); txt(d,(x+85,26),s,31,anchor='lm')
txt(d,(right,26),'终值 19',30,fill=BLUE,anchor='rt')
save(im,'fig8-traffic.png')

observed=[r for r in vehicles if r['observed'].lower()=='true']
video_hash=hashlib.sha256((ROOT/'backend/data/videos/demo.mp4').read_bytes()).hexdigest()
summary={'run_id':RUN.name,'source_sha256':video_hash,'identity_matches':video_hash[:24]==json.loads((RUN/'run.json').read_text())['video_identity'],'statistics_rows':len(rows),'interval_seconds':[float(rows[0]['timestamp']),float(rows[-1]['timestamp'])],'vehicle_rows':len(vehicles),'observed_rows':len(observed),'predicted_rows':len(vehicles)-len(observed),'unique_track_ids':len({r['vehicle_id'] for r in vehicles}),'max_active_tracks':max(int(r['vehicle_count']) for r in rows),'machine_crossings':max(int(r['flow']) for r in rows),'valid_observed_speed_samples':sum(bool(r['speed']) for r in observed),'machine_events':len(list(csv.DictReader((RUN/'events.csv').open(encoding='utf-8-sig')))),'calibrated':False,'analysis':'descriptive machine output; no human truth'}
(OUT/'evidence/run-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
sources=['README.md','CHANGELOG.md','models.json','config.yaml','backend/processor.py','backend/vision/detector.py','backend/vision/tracker.py','backend/vision/video_reader.py','backend/vision/weights.py','backend/calibration/homography.py','backend/traffic/speed_estimator.py','backend/traffic/flow_counter.py','backend/traffic/traffic_metrics.py','backend/events/rules.py','backend/service.py','backend/main.py','backend/exporter.py','backend/reports.py','backend/evidence.py','backend/camera_templates.py','backend/annotations.py','backend/evaluation.py','frontend/src/App.tsx','frontend/src/components/DigitalTwin.tsx','frontend/src/components/VideoView.tsx','frontend/src/utils/snapshotState.ts','frontend/src/utils/twinGeometry.ts','docs/features-analysis.md','docs/accuracy-evaluation.md','docs/visual-evaluation.md','docs/camera-templates.md','docs/twin-orientation.md','plans/002-verification.md','plans/2026-10-02-feature-verification.md','plans/2026-10-02-implementation-status.md','plans/002-browser-result.json','docs/review-smoke-2026-10-02.json']
sources += [str(p.relative_to(ROOT)) for p in (ROOT/'tests').glob('*.py')]+[str(p.relative_to(ROOT)) for p in (ROOT/'frontend/tests').glob('*.mjs')]+[str(p.relative_to(ROOT)) for p in (ROOT/'scripts').glob('*.py')]
sources += [str(p.relative_to(ROOT)) for p in RUN.glob('*') if p.is_file()]
manifest=[]
for i,p in enumerate(sources,1):
    f=ROOT/p
    manifest.append({'evidence_id':f'E{i:03d}','path':p,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'verification':{'source_opened':True,'status':'unverified','verified_by':'','verified_on':''},'assistant_inspected_on':'2026-10-03','human_verification':'pending'})
(OUT/'evidence/source_manifest.json').write_text(json.dumps({'schema_version':'1.0','sources':manifest,'submission_ready':False,'note':'Local evidence opened and checked by Codex; no accountable human verification is claimed.'},ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
