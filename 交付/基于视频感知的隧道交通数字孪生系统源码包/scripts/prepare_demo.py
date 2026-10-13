"""Prepare only the supplied video's image annotations; never invent metric dimensions."""
import argparse
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.settings import DATA
from backend.vision.video_reader import VideoReader,video_identity
parser=argparse.ArgumentParser()
parser.add_argument('--video',help='要复制为内置演示的视频路径，可选')
args=parser.parse_args()
target=DATA/'videos/demo.mp4'
if args.video:
    source=Path(args.video).expanduser().resolve()
    reader=VideoReader(source);reader.close()
    if source!=target.resolve():shutil.copy2(source,target)
if not target.exists():
    print('尚未准备演示视频，启动后可在页面中上传/导入。')
    sys.exit(0)
identity=video_identity(target)
template=json.loads((ROOT/'examples/demo_scene.json').read_text(encoding='utf-8'))
if identity==template['video_identity']:
    scene_path=DATA/'calibrations'/f'{identity}-scene.json'
    if not scene_path.exists():
        scene=dict(lanes=template['lanes'],counting_line=template['counting_line'])
        scene_path.write_text(json.dumps(scene,ensure_ascii=False,indent=2),encoding='utf-8')
    print('已准备提供的桥梁视频、演示车道和计数线；未设置真实尺度。')
else:
    print('视频已准备。导入时会按视频宽高自动生成计数线；可在页面调整车道、计数线和标定区域。')
