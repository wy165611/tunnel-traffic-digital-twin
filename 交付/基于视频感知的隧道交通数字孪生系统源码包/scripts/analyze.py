"""Analyze a recording using the same pipeline as the UI (no model training)."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.settings import DATA, load_config
from backend.api.schemas import SceneInput
from backend.calibration.homography import RoadCalibration
from backend.vision.video_reader import VideoReader, video_identity
from backend.vision.detector import VehicleDetector
from backend.processor import TrafficProcessor
from backend.traffic.counting_line import resolve_counting_line


def main():
    parser = argparse.ArgumentParser(description='离线分析视频并导出 CSV，不训练模型')
    parser.add_argument('--video', required=True)
    parser.add_argument('--calibration', help='包含 points、width_m、length_m 的实测标定 JSON')
    parser.add_argument('--scene', help='包含 counting_line、lanes 的 JSON')
    parser.add_argument('--model', choices=['visdrone_yolo11n', 'coco_yolo11n', 'ssdlite320_mobilenet_v3_large'])
    args = parser.parse_args()
    for name in ('video', 'calibration', 'scene'):
        supplied = getattr(args, name)
        if supplied and not Path(supplied).is_file():
            parser.error(f'--{name} 文件不存在或不可读取：{supplied}')
    config = load_config()
    if args.model:
        config['detector']['model'] = args.model
    reader = processor = None
    try:
        reader = VideoReader(args.video, config['video']['display_max_side'])
        identity = video_identity(args.video)
        cal_path = Path(args.calibration) if args.calibration else DATA / 'calibrations' / f'{identity}-calibration.json'
        scene_path = Path(args.scene) if args.scene else DATA / 'calibrations' / f'{identity}-scene.json'
        calibration = RoadCalibration.load(cal_path)
        scene = json.loads(scene_path.read_text(encoding='utf-8')) if scene_path.exists() else dict(lanes=[], counting_line=None)
        scene = SceneInput.model_validate(scene).model_dump(include={'lanes', 'counting_line', 'counting_line_mode'})
        for point in [*(calibration.points.tolist() if calibration else []), *(scene['counting_line'] or []), *(p for lane in scene['lanes'] for p in lane['points'])]:
            if not (0 <= point[0] <= reader.width and 0 <= point[1] <= reader.height):
                raise ValueError('标定、车道或计数线坐标超出原视频尺寸')
        scene = resolve_counting_line(scene, reader.width, reader.height)
        processor = TrafficProcessor(reader, VehicleDetector(config['detector']), config, scene, calibration)
        processor.exporter.update_metadata(video_id=Path(args.video).name, video_identity=identity, segment_start=0, calibrated=calibration is not None,
                                           config=config, scene=scene, calibration=calibration.payload if calibration else None)
        while (frame := processor.step()) is not None:
            if frame['frame'] % 30 == 0:
                print(f"Frame {frame['frame']}/{reader.frames}: vehicles={frame['metrics']['vehicle_count']} flow={frame['metrics']['total_flow']}", flush=True)
        print('CSV 已保存:', processor.exporter.directory)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    finally:
        if processor:
            processor.close()
        if reader:
            reader.close()


if __name__ == '__main__':
    main()
