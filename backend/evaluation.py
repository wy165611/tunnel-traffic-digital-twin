"""Compare exported traffic measurements with explicitly verified human truth."""
import csv
import json
import math
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment


def finite(value, name):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f'{name} 必须为有限数值')
    return number


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))


def evaluate_run(directory, truth, tolerance=.15):
    directory = Path(directory)
    if truth.get('schema_version') == 2:
        return evaluate_partial(directory, truth, tolerance)
    tolerance = finite(tolerance, '时间容差')
    if not 0 < tolerance <= 5:
        raise ValueError('时间容差须在 (0, 5] 秒')
    metadata = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
    if truth.get('schema_version') != 1 or truth.get('verified') is not True or not isinstance(truth.get('annotator'), str) or not truth['annotator'].strip():
        raise ValueError('真值须声明 schema_version=1、verified=true 和人工核验者 annotator')
    if not metadata.get('video_identity') or truth.get('video_identity') != metadata['video_identity']:
        raise ValueError('真值与统计段的 video_identity 不一致；旧段缺少元数据时须重新分析')
    start, end = [finite(x, 'interval') for x in truth['interval']]
    if start < 0 or end <= start:
        raise ValueError('真值 interval 须为非负起点且终点大于起点')
    for name in ('crossings', 'speeds', 'events'):
        if not isinstance(truth.get(name), list):
            raise ValueError(f'真值须包含 {name} 数组；空数组表示已核验没有对应目标')
        for item in truth[name]:
            timestamp = finite(item['timestamp'], name + '.timestamp')
            if not start <= timestamp <= end:
                raise ValueError('真值条目超出核验区间')
    truth = {**truth, **{name: [{**item, 'timestamp': float(item['timestamp'])} for item in truth[name]] for name in ('crossings', 'speeds', 'events')}}
    stats = rows(directory / 'traffic_statistics.csv')
    if not stats:
        raise ValueError('统计段尚无数据')
    times = [finite(x['timestamp'], 'CSV timestamp') for x in stats]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('统计段时间戳须严格递增')
    if start < times[0] or end > times[-1]:
        raise ValueError('核验区间须完全位于已导出的统计段内')
    before = [x for x, t in zip(stats, times) if t < start]
    within = [x for x, t in zip(stats, times) if start <= t <= end]
    if not within:
        raise ValueError('核验区间内没有统计帧')
    measured_count = int(within[-1]['flow']) - (int(before[-1]['flow']) if before else 0)
    expected_count = len(truth['crossings'])
    vehicles = rows(directory / 'vehicles.csv')
    by_id = {}
    for vehicle in vehicles:
        if vehicle['observed'].lower() != 'true' or not vehicle['speed']:
            continue
        timestamp = finite(vehicle['timestamp'], 'vehicle.timestamp')
        if start <= timestamp <= end:
            by_id.setdefault(int(vehicle['vehicle_id']), []).append((timestamp, finite(vehicle['speed'], 'vehicle.speed')))
    errors = []
    from collections import defaultdict
    grouped = defaultdict(list)
    for item in truth['speeds']:
        speed = finite(item['speed_kmh'], 'speed_kmh')
        if speed < 0:
            raise ValueError('真值速度不可为负')
        grouped[int(item['vehicle_id'])].append(item)
    forbidden_unit = tolerance + 1
    for vehicle_id, items in grouped.items():
        candidates = by_id.get(vehicle_id, [])
        if not items or not candidates:
            continue
        forbidden = (min(len(items), len(candidates)) + 1) * forbidden_unit
        cost = np.full((len(items), len(candidates)), forbidden)
        for i, item in enumerate(items):
            for j, (sample_time, sample_speed) in enumerate(candidates):
                delta = abs(sample_time - item['timestamp'])
                if delta <= tolerance:
                    cost[i, j] = delta
        row_ind, col_ind = linear_sum_assignment(cost)
        for i, j in zip(row_ind, col_ind):
            if cost[i, j] < forbidden:
                errors.append(candidates[j][1] - finite(items[i]['speed_kmh'], 'speed_kmh'))
    predicted = [x for x in rows(directory / 'events.csv') if start <= finite(x['timestamp'], 'event.timestamp') <= end]
    expected = truth['events']
    supported_events = {'ABNORMAL STOP', 'HARD BRAKING', 'WRONG WAY'}
    for item in expected:
        if item['event'] not in supported_events:
            raise ValueError('真值 event 仅支持 ABNORMAL STOP / HARD BRAKING / WRONG WAY')
    matches = 0
    if predicted and expected:
        forbidden = (min(len(predicted), len(expected)) + 1) * (tolerance + 1)
        cost = np.full((len(predicted), len(expected)), forbidden)
        for i, actual in enumerate(predicted):
            for j, target in enumerate(expected):
                delta = abs(float(actual['timestamp']) - target['timestamp'])
                if actual['event'] == target['event'] and int(actual['vehicle_id']) == int(target['vehicle_id']) and delta <= tolerance:
                    cost[i, j] = delta
        selected = linear_sum_assignment(cost)
        matches = int(np.sum(cost[selected] < forbidden))
    return dict(schema_version=1, run_id=metadata['run_id'], video_identity=metadata['video_identity'],
                annotator=truth['annotator'], interval=[start, end], tolerance_seconds=tolerance,
                flow=dict(predicted=measured_count, truth=expected_count, absolute_error=abs(measured_count - expected_count)),
                speed=dict(truth_samples=len(truth['speeds']), matched_samples=len(errors),
                           coverage=len(errors) / len(truth['speeds']) if truth['speeds'] else None,
                           mae_kmh=float(np.mean(np.abs(errors))) if errors else None,
                           rmse_kmh=float(np.sqrt(np.mean(np.square(errors)))) if errors else None),
                events=dict(predicted=len(predicted), truth=len(expected), true_positive=matches,
                            false_positive=len(predicted) - matches, false_negative=len(expected) - matches,
                            precision=matches / len(predicted) if predicted else None,
                            recall=matches / len(expected) if expected else None))


def partial_csv(path, required):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not set(required).issubset(reader.fieldnames):
            raise ValueError(path.name + ' 缺少必需表头或文件为空')
        values = []
        for row in reader:
            if None in row or any(row.get(key) is None for key in required):
                raise ValueError(path.name + ' 行结构损坏')
            row['timestamp'] = finite(row['timestamp'], 'CSV timestamp')
            if row['timestamp'] < 0:
                raise ValueError('CSV 时间不可为负')
            if 'flow' in required:
                flow = finite(row['flow'], 'CSV flow')
                if flow < 0 or not flow.is_integer():
                    raise ValueError('累计流量必须是非负整数')
                row['flow'] = int(flow)
            if 'vehicle_id' in required:
                vid = finite(row['vehicle_id'], 'CSV vehicle_id')
                if vid <= 0 or not vid.is_integer():
                    raise ValueError('机器事件 ID 必须为正整数')
                row['vehicle_id'] = int(vid)
                if row['event'] not in ('ABNORMAL STOP', 'HARD BRAKING', 'WRONG WAY'):
                    raise ValueError('机器事件类型损坏')
            values.append(row)
        return values


def partial_dimensions(directory, metadata, truth, bound):
    video = metadata.get('video')
    if not isinstance(video, dict) or not all(isinstance(video.get(k), int) and not isinstance(video[k], bool) and video[k] > 0 for k in ('width', 'height')):
        from backend.reports import read_json
        stored = read_json(directory / 'annotations.json', {})
        video = stored.get('source_video')
        if not video or any(stored.get(key) != expected for key, expected in [('run_id', metadata.get('run_id')), ('video_identity', metadata.get('video_identity')), ('run_fingerprint', bound)]):
            raise ValueError('旧段缺少来源尺寸；须先通过可验证原视频在界面保存独立来源事实')
        from backend.annotations import SourceVideo
        video = SourceVideo.model_validate(video).model_dump(mode='json')
        if truth.get('source_video') != video:
            raise ValueError('人工文档来源事实与已保存的来源事实不一致')
        if stored.get('dimensions') != [video.get('width'), video.get('height')]:
            raise ValueError('已保存的来源尺寸事实损坏')
    if truth['dimensions'] != [video.get('width'), video.get('height')]:
        raise ValueError('人工文档 dimensions 与统计段来源尺寸不一致')


def evaluate_partial(directory, truth, tolerance=.15):
    """Schema 2 retains schema 1 inclusive counting and one-to-one mapped event semantics."""
    from backend.annotations import AnnotationDocument, fingerprint
    truth = AnnotationDocument.model_validate(truth).model_dump(mode='json')
    if not truth['verified']:
        raise ValueError('人工文档尚未完整核验，不能生成正式指标')
    metadata = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
    if not isinstance(metadata, dict) or metadata.get('status') not in ('closed', 'completed'):
        raise ValueError('只有已关闭或完成的统计段可正式评测')
    if truth['run_id'] != metadata.get('run_id') or truth['video_identity'] != metadata.get('video_identity') or truth['run_fingerprint'] != fingerprint(metadata):
        raise ValueError('人工文档与保存统计段的身份或配置绑定不一致')
    partial_dimensions(directory, metadata, truth, fingerprint(metadata))
    tolerance = finite(tolerance, '时间容差')
    if not 0 < tolerance <= 5:
        raise ValueError('时间容差须在 (0, 5] 秒')
    stats = partial_csv(directory / 'traffic_statistics.csv', ('timestamp', 'flow'))
    times = [finite(row['timestamp'], 'CSV timestamp') for row in stats]
    start, end = truth['interval']
    if not times or any(b <= a for a, b in zip(times, times[1:])) or any(b['flow'] < a['flow'] for a,b in zip(stats,stats[1:])) or start < times[0] or end > times[-1]:
        raise ValueError('核验区间須完全位于已导出的递增统计时间内')
    within = [row for row, t in zip(stats, times) if start <= t <= end]
    if not within:
        raise ValueError('核验区间内没有统计帧')
    before = [row for row, t in zip(stats, times) if t < start]
    flow = dict(available=False, predicted=None, truth=None, absolute_error=None, reason='过线类别未完成核验')
    if 'crossings' in truth['reviewed_sections']:
        measured = int(within[-1]['flow']) - (int(before[-1]['flow']) if before else 0)
        count = len(truth['crossings'])
        flow = dict(available=True, predicted=measured, truth=count, absolute_error=abs(measured-count))
    event_result = dict(available=False, predicted=None, truth=None, true_positive=None, false_positive=None, false_negative=None, precision=None, recall=None, reason='事件类别未完成核验')
    if 'events' in truth['reviewed_sections']:
        predicted = [row for row in partial_csv(directory / 'events.csv', ('timestamp', 'vehicle_id', 'event')) if start <= row['timestamp'] <= end]
        expected = truth['events']
        matches = 0
        if predicted and expected:
            forbidden = (min(len(predicted), len(expected)) + 1) * (tolerance + 1)
            cost = np.full((len(predicted), len(expected)), forbidden)
            for i, actual in enumerate(predicted):
                for j, target in enumerate(expected):
                    delta = abs(float(actual['timestamp']) - target['timestamp'])
                    if target['vehicle_id'] is not None and actual['event'] == target['event'] and int(actual['vehicle_id']) == target['vehicle_id'] and delta <= tolerance:
                        cost[i, j] = delta
            selected = linear_sum_assignment(cost)
            matches = int(np.sum(cost[selected] < forbidden))
        event_result = dict(available=True, predicted=len(predicted), truth=len(expected), true_positive=matches,
                            false_positive=len(predicted)-matches, false_negative=len(expected)-matches,
                            precision=matches/len(predicted) if predicted else None, recall=matches/len(expected) if expected else None,
                            unmapped_truth=sum(item['vehicle_id'] is None for item in expected))
    return dict(schema_version=2, run_id=truth['run_id'], video_identity=truth['video_identity'], run_fingerprint=truth['run_fingerprint'],
                annotation_revision=truth['revision'], annotator=truth['annotator'], interval=[start,end], tolerance_seconds=tolerance,
                reviewed_sections=truth['reviewed_sections'], flow=flow,
                speed=dict(available=False, truth_samples=None, matched_samples=None, coverage=None, mae_kmh=None, rmse_kmh=None,
                           reason='本界面未核验速度，空数组不代表已确认没有速度目标'), events=event_result,
                note='人工区间与所选完整类别的对照结果；不提供整体准确率。无系统映射的人工事件保留为漏报，不作为通配匹配。')
