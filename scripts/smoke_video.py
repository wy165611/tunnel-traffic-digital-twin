"""Real-video end-to-end smoke test; exports observations without metric calibration."""
import argparse
import csv
import json
from pathlib import Path
import sys
import time
import os
import tempfile
from collections import Counter
import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# Keep routine verification out of the user's runs/calibrations/model cache.
isolated = 'TWIN_DATA_DIR' not in os.environ
sandbox = tempfile.TemporaryDirectory(prefix='twin-smoke-') if isolated else None
if sandbox:
    data = Path(sandbox.name)
    for record in json.loads((ROOT/'models.json').read_text()):
        target = data/'models'/record['filename']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(ROOT/'backend/data/models'/record['filename'])
    os.environ['TWIN_DATA_DIR'] = str(data)
from backend.settings import load_config
from backend.vision.video_reader import VideoReader, video_identity
from backend.vision.detector import VehicleDetector
from backend.processor import TrafficProcessor

parser = argparse.ArgumentParser()
parser.add_argument('--video', default=str(ROOT/'backend/data/videos/demo.mp4'))
parser.add_argument('--output', type=Path, help='可选验证记录路径；默认仅输出，不覆盖旧报告')
args = parser.parse_args()
config = load_config()
reader = VideoReader(args.video, config['video']['display_max_side'])
detector = VehicleDetector(config['detector'])
w,h=reader.width,reader.height
scene=dict(counting_line=[[w*.05,h*.72],[w*.95,h*.72]],lanes=[
    dict(name='Left carriageway',points=[[0,h*.45],[w*.58,h*.45],[w*.45,h],[0,h]],direction=[1,-1]),
    dict(name='Right carriageway',points=[[w*.58,h*.45],[w,h*.45],[w,h],[w*.45,h]],direction=[-1,1])])
processor=TrafficProcessor(reader,detector,config,scene)
processor.exporter.update_metadata(video_id=Path(args.video).name, video_identity=video_identity(args.video), segment_start=0, calibrated=False, scene=scene, calibration=None, config=config)
counts,ids,continuities=[],Counter(),[]
start=time.perf_counter();previous=set();last=None
try:
    while (snapshot:=processor.step()) is not None:
        last=snapshot;counts.append(len(snapshot['vehicles']))
        active={v['id'] for v in snapshot['vehicles']}
        if previous:continuities.append(len(active&previous)/len(previous))
        previous=active
        for v in snapshot['vehicles']:
            ids[v['id']]+=1
            assert v['speed'] is None and v['acceleration'] is None and v['world'] is None
        if snapshot['frame']%30==0:print('frame',snapshot['frame'],'active',len(active),flush=True)
finally:
    elapsed=time.perf_counter()-start;processor.close();reader.close()
assert last and max(counts)>0, 'No actual vehicles detected'
assert max(ids.values())>30, 'Tracking IDs did not persist'
assert max(len(v['trajectory']) for v in last['vehicles'])>10, 'No trajectories'
assert last['metrics']['total_flow']>0, 'No crossings counted'
for name in ('vehicles','traffic_statistics','events'):
    with (processor.exporter.directory/f'{name}.csv').open(encoding='utf-8-sig') as f:
        assert csv.DictReader(f).fieldnames
report=dict(video=reader.metadata,model=detector.model_name,device=detector.device,
    frames_processed=len(counts),elapsed_seconds=round(elapsed,2),throughput_fps=round(len(counts)/elapsed,2),
    max_active_vehicles=max(counts),unique_confirmed_ids=len(ids),longest_id_frames=max(ids.values()),
    consecutive_frame_id_retention=round(sum(continuities)/len(continuities),4),
    counted_crossings=last['metrics']['total_flow'],events=last['metrics']['event_count'],
    run_id=processor.exporter.run_id,calibrated=False,
    note='Detection smoke checks, not precision/recall or ID-switch ground truth evaluation. Counting line and carriageway regions are test annotations, not surveyed geometry.')
report['isolated_data'] = isolated
if args.output:
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))

if sandbox: sandbox.cleanup()
