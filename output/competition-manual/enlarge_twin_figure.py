from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
out=Path(__file__).resolve().parent
root=out.parents[1]
im=Image.open(root/'output/playwright/twin-horizontal.png').convert('RGB')
raw=Image.new('RGB',(1288,415),'white');raw.paste(im.crop((0,118,1288,476)),(0,50))
plate=Image.new('RGB',(1288,730),'white');plate.paste(raw,(0,0))
d=ImageDraw.Draw(plate); font=ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc',42)
for x,text in [(315,'实际视频检测视图'),(960,'同帧二维孪生视图')]: d.text((x,23),text,font=font,fill='#172d3a',anchor='mm')
# Enlarged crops from the same original pixels, preserving aspect ratio.
for source,x in [((45,140,190,215),75),((685,150,820,225),790)]:
 crop=raw.crop(source);crop=crop.resize((crop.width*3,crop.height*3),Image.Resampling.LANCZOS)
 plate.paste(crop,(x,480));d.rectangle((x-1,479,x+crop.width,480+crop.height),outline='#b7c4cc',width=2)
d.text((644,448),'同一帧轨迹 ID 1 的局部放大',font=font,fill='#172d3a',anchor='mm')
plate.save(out/'assets/fig4-twin.png',dpi=(300,300))
