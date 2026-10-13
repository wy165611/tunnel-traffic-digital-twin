"""Versioned saved road configurations. Template names are never file paths."""
import copy
import math
import re
import threading
from datetime import datetime, timezone
from contextlib import contextmanager
from uuid import uuid4
from backend.api.schemas import SceneInput
from backend.calibration.homography import RoadCalibration
from backend.exporter import atomic_json
from backend.reports import read_json

ID = re.compile(r'[a-f0-9]{32}')
ASPECT_TOLERANCE = .01
MAX_TEMPLATES = 100
_lock = threading.RLock()


class TemplateConflict(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def text(value, name, limit, required=False):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'{name} 最多 {limit} 字')
    value = value.strip()
    if required and not value:
        raise ValueError(f'{name} 不能为空')
    return value


def folder(data):
    path = data / 'camera_templates'
    if path.is_symlink():
        raise ValueError('模板存储路径无效')
    path.mkdir(exist_ok=True)
    return path


def path_for(data, template_id):
    if not ID.fullmatch(template_id):
        raise ValueError('无效模板 ID')
    path = folder(data) / (template_id + '.json')
    if path.is_symlink():
        raise ValueError('模板路径无效')
    return path


def template_value(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
        return None
    value = read_json(path)
    if not value or value.get('schema_version') != 1 or value.get('id') != path.stem:
        return None
    if not isinstance(value.get('revision'), int) or isinstance(value['revision'], bool) or value['revision'] < 1:
        return None
    if not all(isinstance(value.get(key), str) for key in ('name', 'note', 'created_at', 'updated_at')):
        return None
    if not value['name'].strip() or len(value['name']) > 60 or len(value['note']) > 1000:
        return None
    source = value.get('source')
    if not isinstance(source, dict) or not isinstance(source.get('dimensions'), list) or len(source['dimensions']) != 2:
        return None
    if not all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in source['dimensions']):
        return None
    if not isinstance(value.get('scene'), dict) or (value.get('calibration') is not None and not isinstance(value['calibration'], dict)):
        return None
    return value


def list_templates(data):
    with _lock:
        values = []
        for path in sorted(folder(data).glob('*.json')):
            if not ID.fullmatch(path.stem) or path.is_symlink():
                continue
            value = template_value(path)
            if value and value.get('schema_version') == 1 and value.get('id') == path.stem:
                values.append(value)
        return sorted(values, key=lambda value: value['updated_at'], reverse=True)


def get_template(data, template_id, revision=None):
    with _lock:
        value = template_value(path_for(data, template_id))
        if not value or value.get('schema_version') != 1 or value.get('id') != template_id:
            raise FileNotFoundError('模板不存在或已删除')
        if revision is not None and value['revision'] != revision:
            raise TemplateConflict('模板已被其他窗口更新，请重新选择并预览')
        return copy.deepcopy(value)


@contextmanager
def template_transaction(data, template_id, revision):
    """Service lock is acquired first; hold storage revision through road commit."""
    with _lock:
        get_template(data, template_id, revision)
        yield


def ensure_unique(data, name, exclude=None):
    if any(item['id'] != exclude and item['name'].casefold() == name.casefold() for item in list_templates(data)):
        raise ValueError('模板名称已存在')


def validate_scene(scene, calibration, dimensions):
    width, height = dimensions
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0 for value in dimensions):
        raise ValueError('来源尺寸无效')
    payload = SceneInput(**{key: scene.get(key) for key in ('counting_line', 'counting_line_mode', 'lanes')}, **(calibration or {}))
    value = payload.model_dump(mode='json', exclude={'video_token', 'scene_revision'})
    points = list(value.get('points') or []) + list(value.get('counting_line') or [])
    for lane in value['lanes']:
        points.extend(lane['points'])
    if any(not (0 <= p[0] <= width and 0 <= p[1] <= height) for p in points):
        raise ValueError('模板绘制坐标超出画面')
    if calibration:
        RoadCalibration(value)
    return value


def create_template(data, service, name, note):
    with _lock:
        name, note = text(name, '名称', 60, True), text(note, '备注', 1000)
        ensure_unique(data, name)
        if len(list_templates(data)) >= MAX_TEMPLATES:
            raise ValueError('最多保存 100 个模板，请删除不需要的模板')
        if not service.reader:
            raise ValueError('请先选择视频')
        dimensions = [service.reader.width, service.reader.height]
        scene = {key: copy.deepcopy(service.scene.get(key)) for key in ('counting_line', 'counting_line_mode', 'lanes')}
        calibration = copy.deepcopy(service.calibration.payload) if service.calibration else None
        validate_scene(scene, calibration, dimensions)
        created = now()
        value = dict(schema_version=1, id=uuid4().hex, revision=1, name=name, note=note,
                     created_at=created, updated_at=created,
                     source=dict(video_id=service.video_id, video_identity=service.identity, dimensions=dimensions),
                     scene=scene, calibration=calibration)
        atomic_json(path_for(data, value['id']), value)
        return value


def rename_template(data, template_id, revision, name, note):
    with _lock:
        value = get_template(data, template_id, revision)
        name, note = text(name, '名称', 60, True), text(note, '备注', 1000)
        ensure_unique(data, name, template_id)
        value.update(name=name, note=note, revision=value['revision'] + 1, updated_at=now())
        atomic_json(path_for(data, template_id), value)
        return value


def delete_template(data, template_id, revision):
    with _lock:
        get_template(data, template_id, revision)
        path_for(data, template_id).unlink()


def preview_template(data, service, template_id, revision):
    template = get_template(data, template_id, revision)
    if not service.reader:
        raise ValueError('请先选择目标视频')
    source = template['source']['dimensions']
    target = [service.reader.width, service.reader.height]
    validate_scene(template['scene'], template['calibration'], source)
    ratio_difference = abs((target[0]/target[1])/(source[0]/source[1]) - 1)
    applicable = ratio_difference <= ASPECT_TOLERANCE + 1e-9
    mapped = copy.deepcopy(template['scene'])
    point = lambda p: [p[0]*target[0]/source[0], p[1]*target[1]/source[1]]
    if mapped['counting_line']:
        mapped['counting_line'] = [point(p) for p in mapped['counting_line']]
    for lane in mapped['lanes']:
        lane['points'] = [point(p) for p in lane['points']]
    calibration = copy.deepcopy(template['calibration'])
    if calibration:
        calibration['points'] = [point(p) for p in calibration['points']]
    validate_scene(mapped, calibration, target)
    return dict(template_id=template_id, template_revision=template['revision'], name=template['name'],
                video_token=service.video_token, scene_revision=service.scene_revision,
                source=template['source'], target_dimensions=target, scene=mapped, calibration=calibration,
                applicable=applicable, aspect_difference=ratio_difference, aspect_tolerance=ASPECT_TOLERANCE,
                reasons=[] if applicable else ['画面宽高比差异超过 1%，只能预览；请在当前画面重新绘制'],
                warning='分辨率或宽高比相同不能证明机位、视野、裁切、旋转或缩放相同；必须人工核对几何。')
