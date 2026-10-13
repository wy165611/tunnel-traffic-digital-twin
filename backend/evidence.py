"""Immutable machine captures and separate, atomic human reviews."""
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import cv2
from backend.exporter import atomic_json
from backend.reports import read_json, rows, run_directory, display_lane
from backend.events.rules import EVENT_NAMES
from backend.vision.video_reader import video_identity

EVENT_PATTERN = re.compile(r'[a-f0-9]{32}')
REVIEW_STATUSES = ('pending', 'confirmed', 'false_positive')
_review_lock = threading.RLock()


def capture_event(exporter, event, vehicle, frame, index, reader, config, scene, calibration):
    event_id = uuid4().hex
    event.update(event_id=event_id, run_id=exporter.run_id)
    with exporter.lock:
        directory = exporter.directory / 'evidence'
        directory.mkdir(exist_ok=True)
        temporary = directory / (event_id + '.tmp')
        final = directory / event_id
        temporary.mkdir()
        try:
            image = frame.copy()
            sx, sy = reader.display_width / reader.width, reader.display_height / reader.height
            x1, y1, x2, y2 = vehicle['box']
            box = [round(x1*sx), round(y1*sy), round(x2*sx), round(y2*sy)]
            box = [max(0, min(reader.display_width-1, box[0])), max(0, min(reader.display_height-1, box[1])),
                   max(0, min(reader.display_width-1, box[2])), max(0, min(reader.display_height-1, box[3]))]
            cv2.rectangle(image, tuple(box[:2]), tuple(box[2:]), (50, 80, 255), 2)
            cv2.putText(image, f"#{vehicle['id']} {event['event']}", (box[0], max(18, box[1]-6)), cv2.FONT_HERSHEY_SIMPLEX, .45, (50, 80, 255), 1)
            if not cv2.imwrite(str(temporary / 'screenshot.jpg'), image):
                raise OSError('无法保存报警截图')
            metadata = dict(event=event.copy(), frame=index, timestamp=event['timestamp'],
                            original_dimensions=[reader.width, reader.height], display_dimensions=[reader.display_width, reader.display_height],
                            display_box=box, vehicle=vehicle, observed_trajectory=vehicle['world_trajectory'],
                            rule_config=config['events'], legal_direction=next((lane.get('direction') for lane in scene.get('lanes', []) if lane['name'] == vehicle['lane']), config['traffic']['legal_direction']),
                            calibration=calibration.payload if calibration else None,
                            source={key: exporter.metadata.get(key) for key in ('video_id', 'video_identity', 'segment_start')},
                            created_at=datetime.now(timezone.utc).isoformat())
            atomic_json(temporary / 'capture.json', metadata)
            temporary.rename(final)
        finally:
            if temporary.exists():
                import shutil
                shutil.rmtree(temporary)
    return event


def evidence_directory(data, run_id, event_id):
    run = run_directory(data, run_id)
    if not EVENT_PATTERN.fullmatch(event_id):
        raise ValueError('无效事件 ID')
    folder = run / 'evidence' / event_id
    if not folder.is_dir() or (run / 'evidence').is_symlink() or folder.is_symlink() or folder.resolve().parent != run / 'evidence':
        raise FileNotFoundError('此事件未保存证据（可能是旧统计段）')
    return run, folder


def source_path(data, source):
    filename, identity = source.get('video_id'), source.get('video_identity')
    if not filename or not identity or Path(filename).name != filename:
        return None, '缺少来源身份，无法验证原视频'
    root = (Path(data) / 'videos').resolve()
    path = root / filename
    if not path.is_file() or path.resolve().parent != root:
        return None, '原视频不存在或路径不可用'
    try:
        if video_identity(path) != identity:
            return None, '原视频内容已改变；仍可查看保存的截图'
    except OSError:
        return None, '原视频无法读取'
    return path, None


def event_detail(data, run_id, event_id):
    run, folder = evidence_directory(data, run_id, event_id)
    capture = read_json(folder / 'capture.json')
    if not capture:
        raise FileNotFoundError('报警证据元数据不可用')
    with _review_lock:
        review = read_json(run / 'reviews.json', {}).get(event_id, dict(status='pending', note='', updated_at=None))
    path, reason = source_path(data, capture.get('source') or {})
    return dict(**capture, review=review, source_available=path is not None, source_reason=reason,
                screenshot_url=f'/api/runs/{run_id}/events/{event_id}/screenshot',
                source_url=f'/api/runs/{run_id}/events/{event_id}/source' if path else None)


def list_events(data, run_id, offset=0, limit=50):
    if offset < 0 or not 1 <= limit <= 200:
        raise ValueError('无效分页参数')
    run = run_directory(data, run_id)
    if not (run / 'events.csv').is_file():
        return dict(items=[], total=None, available=False, offset=offset, limit=limit)
    with _review_lock:
        reviews = read_json(run / 'reviews.json', {})
    metadata = read_json(run / 'run.json', {})
    items, total = [], 0
    for row in rows(run, 'events'):
        row['lane'] = display_lane(row, metadata)
        if offset <= total < offset + limit:
            event_id = row.get('event_id') or None
            items.append({**row, 'run_id': run_id, 'event_id': event_id, 'label': EVENT_NAMES.get(row.get('event'), row.get('event')),
                'evidence_available': bool(event_id and EVENT_PATTERN.fullmatch(event_id) and (run / 'evidence' / event_id / 'capture.json').is_file()),
                'review': reviews.get(event_id, dict(status='pending', note='')) if event_id else None})
        total += 1
    return dict(items=items, total=total, available=True, offset=offset, limit=limit)


def save_review(data, run_id, event_id, status, note):
    run, _ = evidence_directory(data, run_id, event_id)
    if status not in REVIEW_STATUSES or not isinstance(note, str) or len(note) > 1000:
        raise ValueError('复核状态必须有效，备注最多 1000 字')
    review = dict(status=status, note=note, updated_at=datetime.now(timezone.utc).isoformat())
    with _review_lock:
        values = read_json(run / 'reviews.json', {})
        values[event_id] = review
        atomic_json(run / 'reviews.json', values)
    return review
