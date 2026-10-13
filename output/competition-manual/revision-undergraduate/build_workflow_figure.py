from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import math
out=Path(__file__).resolve().parent
im=Image.new('RGB',(1800,430),'white');d=ImageDraw.Draw(im)
font='/System/Library/Fonts/Hiragino Sans GB.ttc'
def f(n):return ImageFont.truetype(font,n)
ink='#172d3a';blue='#245c79';fill='#edf4f7'
def text(x,y,s,n=32):d.text((x,y),s,font=f(n),fill=ink,anchor='mm')
def arrow(a,b):
    d.line([a,b],fill=blue,width=5);ang=math.atan2(b[1]-a[1],b[0]-a[0]);r=20
    d.polygon([b,(b[0]-r*math.cos(ang-.5),b[1]-r*math.sin(ang-.5)),(b[0]-r*math.cos(ang+.5),b[1]-r*math.sin(ang+.5))],fill=blue)
labels=[('选择录像','确认来源与范围'),('配置道路','车道 计数线 标定'),('观察双视图','车辆 轨迹 统计'),('检查报告与证据','历史输出 原始回放'),('人工标注与评测','独立核验 保存版本')]
for i,(a,b) in enumerate(labels):
    x=15+i*360
    d.rounded_rectangle((x,45,x+330,200),radius=15,fill=fill,outline=blue,width=3)
    text(x+165,95,a,34);text(x+165,153,b,28)
    if i<4:arrow((x+330,120),(x+360,120))
arrow((1620,210),(1620,300));arrow((1620,300),(180,300));arrow((180,300),(180,212))
d.rectangle((490,267,1300,332),fill='white');text(895,300,'回查问题与条件  为下一轮验证保留记录',32)
text(900,389,'没有可靠实测尺度时保留速度不可用  来源 配置与标注版本随结果保存',29)
im.save(out/'assets/fig2-pipeline.png',dpi=(300,300))
p=out/'build_revision.py';s=p.read_text()
s=s.replace('图8使用全部统计行','图7使用全部统计行').replace("fig(8,'fig8-traffic.png'","fig(7,'fig8-traffic.png'")
s=s.replace('图7来自受控流程验收','图8来自受控流程验收').replace("fig(7,'fig7-evaluation.png'","fig(8,'fig7-evaluation.png'")
p.write_text(s)
print('Source-derived user workflow figure prepared; figure order corrected.')
