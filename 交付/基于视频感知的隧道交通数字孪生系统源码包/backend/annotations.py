"""Run-bound manual truth, independent original replay and partial-category evaluation."""
import copy
import csv
import hashlib
import json
import math
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.evidence import source_path
from backend.exporter import atomic_json
from backend.reports import read_json, rows, run_directory, snapshot_run, number
from backend.vision.video_reader import VideoReader

MAX_ROWS = 1000
_lock = threading.RLock()
SUPPORTED_EVENTS = ('ABNORMAL STOP', 'HARD BRAKING', 'WRONG WAY')


class AnnotationConflict(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


class Crossing(BaseModel):
    model_config = ConfigDict(extra='forbid')
    timestamp: float = Field(ge=0, allow_inf_nan=False, strict=True)
    physical_vehicle_note: str = Field(default='', max_length=200)


class ManualEvent(Crossing):
    event: Literal['ABNORMAL STOP', 'HARD BRAKING', 'WRONG WAY']
    vehicle_id: int | None = Field(default=None, strict=True, gt=0)

    @model_validator(mode='after')
    def unmapped(self):
        if self.vehicle_id is None and not self.physical_vehicle_note.strip():
            raise ValueError('无系统轨迹 ID 的事件须填写人工物理车辆说明，计入漏报且不会匹配机器事件')
        return self


class SourceVideo(BaseModel):
    model_config = ConfigDict(extra='forbid')
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    fps: float = Field(gt=0, allow_inf_nan=False, strict=True)
    frames: int | None = Field(default=None, ge=0, strict=True)
    duration: float | None = Field(default=None, ge=0, allow_inf_nan=False, strict=True)
    orientation: Literal['landscape', 'portrait', 'square'] | None = None
    display_width: int | None = Field(default=None, gt=0, strict=True)
    display_height: int | None = Field(default=None, gt=0, strict=True)
    duration_estimated: bool | None = Field(default=None, strict=True)
    live: bool | None = Field(default=None, strict=True)
    timing_source: Literal['decoder_pts'] | None = None


class AnnotationDocument(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[2] = 2
    run_id: str = Field(pattern=r'^\d{8}-\d{6}-[a-f0-9]{6}$')
    video_identity: str = Field(pattern=r'^[a-f0-9]{24}$')
    run_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    dimensions: tuple[Annotated[int, Field(strict=True, gt=0)], Annotated[int, Field(strict=True, gt=0)]]
    interval: tuple[Annotated[float, Field(strict=True, allow_inf_nan=False)], Annotated[float, Field(strict=True, allow_inf_nan=False)]]
    source_video: SourceVideo | None = None
    annotator: str = Field(default='', max_length=100)
    note: str = Field(default='', max_length=1000)
    revision: int = Field(default=0, ge=0, strict=True)
    created_at: str | None = Field(default=None, max_length=50)
    updated_at: str | None = Field(default=None, max_length=50)
    crossings: list[Crossing] = Field(default_factory=list, max_length=MAX_ROWS)
    events: list[ManualEvent] = Field(default_factory=list, max_length=MAX_ROWS)
    speeds: list = Field(default_factory=list, max_length=0)
    speed_state: Literal['unreviewed'] = 'unreviewed'
    reviewed_sections: list[Literal['crossings', 'events']] = Field(default_factory=list, max_length=2)
    verified: bool = Field(default=False, strict=True)
    completeness_confirmed: bool = Field(default=False, strict=True)

    @model_validator(mode='after')
    def bounds(self):
        start, end = self.interval
        if not all(math.isfinite(t) for t in self.interval) or start < 0 or end <= start:
            raise ValueError('区间必须是有限非负起点，且结束晚于开始')
        if self.source_video and self.dimensions != (self.source_video.width, self.source_video.height):
            raise ValueError('独立来源事实与文档尺寸不一致')
        if any(isinstance(t, bool) or t <= 0 for t in self.dimensions):
            raise ValueError('来源尺寸无效')
        if len(set(self.reviewed_sections)) != len(self.reviewed_sections):
            raise ValueError('完成类别不能重复')
        for item in self.crossings + self.events:
            if not start <= item.timestamp <= end:
                raise ValueError('人工条目超出所选核验区间')
        if self.verified and (not self.annotator.strip() or not self.reviewed_sections or not self.completeness_confirmed):
            raise ValueError('核验须有姓名、至少一个完整类别与人工完整性声明')
        if not self.verified:
            self.completeness_confirmed = False
        return self


class AnnotationSave(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=0, strict=True)
    document: AnnotationDocument


class EvaluationRequest(BaseModel):
    expected_revision: int = Field(ge=1, strict=True)
    tolerance_seconds: float = Field(default=.15, gt=0, le=5, allow_inf_nan=False)


def fingerprint(metadata):
    for key in ('scene', 'config', 'calibration'):
        if key not in metadata or (key != 'calibration' and not isinstance(metadata[key], dict)):
            raise ValueError('统计段缺少保存的道路、标定或分析参数')
    scene = metadata['scene']
    if 'lanes' not in scene or 'counting_line' not in scene:
        raise ValueError('统计段道路元数据不完整')
    canonical = json.dumps({key: metadata[key] for key in ('scene', 'calibration', 'config')}, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def context_from_snapshot(data, run_id, directory):
    metadata = read_json(directory / 'run.json')
    reasons = []
    if not metadata or metadata.get('run_id') != run_id or not isinstance(metadata.get('video_identity'), str) or not re.fullmatch(r'[a-f0-9]{24}', metadata['video_identity']):
        return dict(available=False, run_id=run_id, reasons=['统计段来源元数据缺失或损坏，请重新分析'], source_available=False, closed=False)
    try:
        bound = fingerprint(metadata)
    except (ValueError, TypeError) as exc:
        return dict(available=False, run_id=run_id, reasons=[str(exc)], source_available=False, closed=False)
    path, source_reason = source_path(data, metadata)
    video = metadata.get('video')
    if not isinstance(video, dict) or not all(number(video.get(k)) and number(video.get(k)) > 0 for k in ('width', 'height', 'fps')):
        video = None
        if path:
            try:
                reader = VideoReader(path)
                try:
                    video = reader.metadata
                finally:
                    reader.close()
            except (ValueError, OSError):
                reasons.append('原视频尺寸无法读取')
    if not video:
        # Preserve independently saved, previously verified source facts for legacy runs.
        # The save endpoint always writes these facts from context, never from imported input.
        saved = read_json(run_directory(data, run_id) / 'annotations.json', {})
        saved_video = saved.get('source_video')
        if saved.get('run_id') == run_id and saved.get('video_identity') == metadata['video_identity'] and saved.get('run_fingerprint') == bound and isinstance(saved_video, dict):
            if all(number(saved_video.get(k)) and number(saved_video.get(k)) > 0 for k in ('width', 'height', 'fps')) and saved.get('dimensions') == [saved_video['width'], saved_video['height']]:
                video = copy.deepcopy(saved_video)
    if not video:
        reasons.append('缺少可核验的来源尺寸')
    else:
        # Live transport state is not a persistent source fact for annotations.
        video = {key: value for key, value in video.items() if key in SourceVideo.model_fields}
    first = last = None
    try:
        if not (directory / 'traffic_statistics.csv').is_file():
            reasons.append('交通统计 CSV 缺失')
        previous = None
        for row in rows(directory, 'traffic_statistics'):
            timestamp = number(row.get('timestamp'))
            flow = number(row.get('flow'))
            if timestamp is None or flow is None or (previous is not None and timestamp <= previous):
                raise ValueError('交通统计 CSV 损坏或时间不递增')
            previous = timestamp
            first = timestamp if first is None else first
            last = timestamp
    except (ValueError, OSError, csv.Error) as exc:
        reasons.append(str(exc))
    if first is None or last is None or last <= first:
        reasons.append('统计段没有可核验的有效区间')
    closed = metadata.get('status') in ('closed', 'completed')
    return dict(available=not reasons, run_id=run_id, video_id=metadata.get('video_id'), video_identity=metadata['video_identity'],
                run_fingerprint=bound, video=video, dimensions=[video['width'], video['height']] if video else None,
                interval=[first, last] if first is not None and last is not None else None,
                scene=metadata['scene'], calibration=metadata['calibration'], config=metadata['config'],
                status=metadata.get('status'), closed=closed, source_available=path is not None, source_reason=source_reason,
                source_url=f'/api/runs/{run_id}/source' if path else None, reasons=reasons,
                verification_allowed=not reasons and closed and path is not None,
                machine_events_available=(directory / 'events.csv').is_file(),
                observations_available=(directory / 'vehicles.csv').is_file(),
                note='人工条目独立于机器报警复核；未选类别未知，速度未评测。仅关闭或完成的段可正式评测。')


def get_context(data, run_id, exporter=None):
    with snapshot_run(data, run_id, exporter) as directory:
        return context_from_snapshot(data, run_id, directory)


def empty_document(context):
    if not context['available']:
        return None
    return AnnotationDocument(run_id=context['run_id'], video_identity=context['video_identity'],
                              run_fingerprint=context['run_fingerprint'], dimensions=context['dimensions'], interval=context['interval'], source_video=context['video']).model_dump(mode='json')


def validate_binding(document, context):
    if not context['available']:
        raise ValueError('该段不可标注：' + '；'.join(context['reasons']))
    for key in ('run_id', 'video_identity', 'run_fingerprint', 'dimensions'):
        if document[key] != context[key]:
            raise ValueError(f'人工文档 {key} 与本统计段不一致，禁止跨段或跨配置导入')
    start, end = document['interval']
    if start < context['interval'][0] or end > context['interval'][1]:
        raise ValueError('核验区间须完全位于该段已导出的范围内')


def load_annotations(data, run_id, exporter=None):
    run = run_directory(data, run_id)
    context = get_context(data, run_id, exporter)
    with _lock:
        stored = read_json(run / 'annotations.json')
        result = read_json(run / 'evaluation.json')
    document = stored if stored else empty_document(context)
    valid_binding = bool(stored and context.get('available') and all(stored.get(key) == context.get(key) for key in ('run_id', 'video_identity', 'run_fingerprint', 'dimensions')))
    stale = bool(result and (not valid_binding or result.get('annotation_revision') != stored.get('revision') or result.get('run_fingerprint') != context.get('run_fingerprint')))
    return dict(document=document, saved=stored is not None, context=context, result=result, result_stale=stale,
                binding_valid=valid_binding if stored else context.get('available', False))


def save_annotations(data, run_id, payload, exporter=None):
    run = run_directory(data, run_id)
    context = get_context(data, run_id, exporter)
    document = payload.document.model_dump(mode='json')
    validate_binding(document, context)
    if document['verified'] and not context['verification_allowed']:
        raise ValueError('原视频缺失/改变或统计段仍在记录，不能作出新的完整核验声明；可保存未核验草稿')
    with _lock:
        old = read_json(run / 'annotations.json')
        revision = old.get('revision', 0) if old else 0
        if payload.expected_revision != revision or document['revision'] != revision:
            raise AnnotationConflict('人工文档已被其他窗口更新，请先导出本地草稿再重新打开')
        document['source_video'] = SourceVideo.model_validate(context['video']).model_dump(mode='json')
        document.update(revision=revision + 1, created_at=old.get('created_at') if old else now(), updated_at=now())
        atomic_json(run / 'annotations.json', document)
        return document


def observations(data, run_id, seconds, exporter=None):
    if not isinstance(seconds, (float, int)) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError('查询时间必须是有限非负秒数')
    with snapshot_run(data, run_id, exporter) as directory:
        context = context_from_snapshot(data, run_id, directory)
        if not context['available']:
            raise ValueError('该段观测不可用：' + '；'.join(context['reasons']))
        if not context['interval'][0] <= seconds <= context['interval'][1]:
            raise ValueError('查询时间超出导出区间')
        if not (directory / 'vehicles.csv').is_file():
            return dict(available=False, reason='车辆 CSV 缺失', requested_seconds=seconds, sample_timestamp=None, items=[])
        with (directory / 'vehicles.csv').open(encoding='utf-8-sig', newline='') as stream:
            headers = csv.DictReader(stream).fieldnames or []
        if not {'timestamp', 'vehicle_id', 'x_pixel', 'y_pixel', 'observed'}.issubset(headers):
            return dict(available=False, reason='旧车辆 CSV 缺少实际观测/像素字段或表头损坏', requested_seconds=seconds, sample_timestamp=None, items=[])
        closest, difference, items, truncated = None, float('inf'), [], False
        for row in rows(directory, 'vehicles'):
            if str(row.get('observed')).lower() != 'true':
                continue
            timestamp = number(row.get('timestamp'))
            x, y, vid = number(row.get('x_pixel')), number(row.get('y_pixel')), number(row.get('vehicle_id'))
            if timestamp is None or x is None or y is None or vid is None or not vid.is_integer() or vid <= 0:
                continue
            delta = abs(timestamp-seconds)
            if delta < difference - 1e-9:
                closest, difference, items, truncated = timestamp, delta, [], False
            if timestamp == closest and len(items) >= 200:
                truncated = True
            if timestamp == closest and len(items) < 200:
                items.append(dict(vehicle_id=int(vid), timestamp=timestamp, pixel=[x, y], vehicle_type=row.get('vehicle_type'), lane=row.get('lane') or None))
        # Distant observations are not a current paused frame measurement.
        if closest is None or difference > .5:
            return dict(available=True, requested_seconds=seconds, sample_timestamp=None, items=[], note='所选时间附近 0.5 秒内没有实际观测样本')
        return dict(available=True, requested_seconds=seconds, sample_timestamp=closest, items=items, truncated=truncated,
                    note='CSV 最邻近实际观测时间（最多相差 0.5 秒）；底部中心点与 ID 仅辅助人工映射，不是真值或检测框')


def evaluate_annotations(data, run_id, expected_revision, tolerance, exporter=None):
    from backend.evaluation import evaluate_run
    run = run_directory(data, run_id)
    with _lock:
        truth = read_json(run / 'annotations.json')
        if not truth:
            raise ValueError('请先保存并完整核验至少一个类别')
        if truth.get('revision') != expected_revision:
            raise AnnotationConflict('评测文档版本已改变，请使用最新保存版本')
        with snapshot_run(data, run_id, exporter) as directory:
            context = context_from_snapshot(data, run_id, directory)
            validate_binding(truth, context)
            if not context['closed']:
                raise ValueError('请先结束当前分析段，再评测已保存的完整区间')
            # Keep prior independently recorded source facts available to the legacy-run evaluator.
            atomic_json(directory / 'annotations.json', truth)
            result = evaluate_run(directory, truth, tolerance)
        result.update(annotation_revision=truth['revision'], run_fingerprint=truth['run_fingerprint'], evaluated_at=now())
        atomic_json(run / 'evaluation.json', result)
        return result
