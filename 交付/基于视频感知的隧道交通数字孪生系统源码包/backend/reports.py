"""Read bounded reports from a consistent run snapshot, without changing live state."""
import csv
import html
import json
import math
import re
import shutil
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

RUN_PATTERN = re.compile(r'\d{8}-\d{6}-[a-f0-9]{6}')
TREND_LIMIT = 300
INTERVAL_TOLERANCE = .1


def run_directory(data, run_id):
    if not RUN_PATTERN.fullmatch(run_id):
        raise ValueError('无效统计段 ID')
    root = (Path(data) / 'runs').resolve()
    directory = root / run_id
    if not directory.is_dir() or directory.is_symlink() or directory.resolve().parent != root:
        raise FileNotFoundError('统计段不存在')
    return directory


def read_json(path, default=None):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else default
    except (OSError, ValueError):
        return default


@contextmanager
def snapshot_run(data, run_id, exporter=None):
    directory = run_directory(data, run_id)
    with tempfile.TemporaryDirectory(prefix='twin-report-') as temporary:
        target = Path(temporary)
        if exporter and exporter.directory == directory:
            exporter.snapshot_all(target)
        else:
            for name in ('run.json', 'vehicles.csv', 'traffic_statistics.csv', 'events.csv', 'lane_statistics.csv', 'reviews.json'):
                if (directory / name).is_file():
                    shutil.copyfile(directory / name, target / name)
        yield target


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def rows(directory, kind):
    path = directory / (kind + '.csv')
    if path.is_file():
        with path.open(encoding='utf-8-sig', newline='') as stream:
            yield from csv.DictReader(stream)


def display_lane(row, metadata=None):
    if row.get('lane_json'):
        try:
            original = json.loads(row['lane_json'])
            if original is None or isinstance(original, str):
                return original
        except (ValueError, TypeError):
            pass
    # Legacy inverse mappings are safe only when one configured name matches.
    from backend.exporter import csv_value
    scene = (metadata or {}).get('scene')
    names = [lane['name'] for lane in (scene.get('lanes') or []) if isinstance(lane, dict) and isinstance(lane.get('name'), str)] if isinstance(scene, dict) else []
    matches = [name for name in names if csv_value(name) == row.get('lane')]
    return matches[0] if len(matches) == 1 else row.get('lane')


class BoundedTrend:
    """Streaming deterministic decimation. Memory stays <= 2*limit."""
    def __init__(self, limit=TREND_LIMIT):
        self.limit, self.step, self.index, self.values, self.last = limit, 1, 0, [], None

    def add(self, value):
        self.last = value
        if self.index % self.step == 0:
            self.values.append(value)
        self.index += 1
        if len(self.values) > self.limit * 2:
            self.values = self.values[::2]
            self.step *= 2

    def result(self):
        result = self.values[:]
        if self.last is not None and (not result or result[-1] != self.last):
            result.append(self.last)
        if len(result) > self.limit:
            result = [result[index * (len(result)-1) // (self.limit-1)] for index in range(self.limit)]
        return result


def build_report(directory, run_id):
    metadata = read_json(directory / 'run.json', {})
    available = {kind: (directory / (kind + '.csv')).is_file() for kind in ('vehicles', 'traffic_statistics', 'events', 'lane_statistics')}
    first = last = None
    flow = None
    trend = BoundedTrend()
    for row in rows(directory, 'traffic_statistics'):
        t = number(row.get('timestamp'))
        if t is None:
            continue
        first = t if first is None else min(first, t)
        last = t if last is None else max(last, t)
        cumulative = number(row.get('flow'))
        if cumulative is not None:
            flow = cumulative if flow is None else max(flow, cumulative)
        trend.add(dict(timestamp=t, vehicle_count=number(row.get('vehicle_count')), flow=cumulative,
                       average_speed=number(row.get('average_speed'))))
    observed_known = False
    if available['vehicles']:
        with (directory / 'vehicles.csv').open(encoding='utf-8-sig', newline='') as stream:
            observed_known = 'observed' in (csv.DictReader(stream).fieldnames or [])
    observed_samples = speed_samples = 0
    speed_total = 0.
    speed_min = speed_max = None
    for row in rows(directory, 'vehicles'):
        observed_known = observed_known or 'observed' in row
        # Legacy records without observed cannot honestly establish observation coverage.
        if str(row.get('observed')).lower() not in ('true', '1'):
            continue
        observed_samples += 1
        speed = number(row.get('speed'))
        if speed is not None:
            speed_samples += 1
            speed_total += speed
            speed_min = speed if speed_min is None else min(speed_min, speed)
            speed_max = speed if speed_max is None else max(speed_max, speed)
    events = Counter()
    event_trend = BoundedTrend(200)
    reviews = read_json(directory / 'reviews.json', {})
    review_counts = Counter()
    for index, row in enumerate(rows(directory, 'events')):
        events[row.get('event') or '未知'] += 1
        row['lane'] = display_lane(row, metadata)
        event_id = row.get('event_id') or None
        status = reviews.get(event_id, {}).get('status', 'pending') if event_id else 'unavailable'
        review_counts[status] += 1
        event_trend.add({**row, 'timestamp': number(row.get('timestamp')), 'speed': number(row.get('speed')),
                            'run_id': run_id, 'event_id': event_id, 'review_status': status})
    lanes = {}
    for row in rows(directory, 'lane_statistics'):
        if number(row.get('timestamp')) is None or number(row.get('window_seconds')) is None:
            continue
        lane = display_lane(row, metadata) or '未划分'
        row['lane'] = lane
        lanes.setdefault(lane, {}).setdefault(row.get('window_seconds', 'unknown'), BoundedTrend()).add({k: (row[k] if k == 'lane' else row[k].lower() == 'true' if k == 'complete' else number(row[k])) for k in row if k != 'lane_json'})
    start = number(metadata.get('segment_start'))
    duration = max(0., last - start) if last is not None and start is not None else None
    return dict(run_id=run_id, metadata=metadata, available=available,
        range=dict(start=start, first_observed=first, end=last, duration=duration),
        summary=dict(cumulative_crossings=flow, machine_event_count=sum(events.values()) if available['events'] else None,
                     event_types=dict(events), review_counts=dict(review_counts)),
        speed=dict(mean=speed_total / speed_samples if speed_samples else None, min=speed_min, max=speed_max,
                   observed_samples=observed_samples if observed_known else None, speed_samples=speed_samples if observed_known else None,
                   coverage=speed_samples / observed_samples if observed_samples else None,
                   definition='仅 observed=true 且速度有效的车辆帧样本；不是每车平均，也不是检测精度'),
        trend=trend.result(), lanes={lane: sorted([row for values in windows.values() for row in values.result()], key=lambda row: (row.get('timestamp') or 0, row.get('window_seconds') or 0)) for lane, windows in lanes.items()},
        events=event_trend.result(), events_truncated=sum(events.values()) > len(event_trend.result()),
        notes=['累计过线取累计列最大值，不对逐帧累计值求和。', '机器报警来自轨迹规则，人工复核单独记录，均不代表真实标签。',
               '缺失数据为不可用；趋势按时间顺序降采样，仅供浏览。'])


def compare_reports(left, right):
    a, b = left['metadata'], right['metadata']
    reasons = []
    identity_a, identity_b = a.get('video_identity'), b.get('video_identity')
    if not identity_a or not identity_b:
        reasons.append('缺少视频内容身份')
    elif identity_a != identity_b:
        reasons.append('视频内容不同')
    for name in ('start', 'end'):
        av, bv = left['range'][name], right['range'][name]
        if av is None or bv is None:
            reasons.append('分析区间信息不完整')
        elif abs(av - bv) > INTERVAL_TOLERANCE:
            reasons.append('分析起止区间不同（容差 0.1 秒）')
    if not isinstance(a.get('scene'), dict) or not isinstance(b.get('scene'), dict):
        reasons.append('缺少计数线或车道配置')
    else:
        for key, label in (('counting_line', '计数线'), ('lanes', '车道')):
            if key not in a['scene'] or key not in b['scene']:
                reasons.append('缺少' + label + '记录')
            elif a['scene'].get(key) != b['scene'].get(key):
                reasons.append(label + '配置不同')
    if 'calibration' not in a or 'calibration' not in b:
        reasons.append('缺少尺度标定记录')
    elif a['calibration'] != b['calibration']:
        reasons.append('尺度标定不同')
    differences = []
    for section in ('detector', 'video', 'speed', 'events', 'tracking', 'traffic'):
        if (a.get('config') or {}).get(section) != (b.get('config') or {}).get(section):
            differences.append(section)
    return dict(comparable=not reasons, reasons=list(dict.fromkeys(reasons)), tolerance_seconds=INTERVAL_TOLERANCE,
                settings_differences=differences, left=left['run_id'], right=right['run_id'],
                note='结果差异仅表示运行输出变化，不能推断准确率提升。')


def svg_trend(points, field, label):
    valid = [(number(row.get('timestamp')), number(row.get(field))) for row in points]
    valid = [(x, y) for x, y in valid if x is not None and y is not None]
    if not valid:
        return '<p>' + html.escape(label) + '：不可用</p>'
    xmin, xmax = min(x for x, _ in valid), max(x for x, _ in valid)
    ymax = max(1., max(y for _, y in valid))
    coordinates = ' '.join(f'{40+(x-xmin)/max(.001,xmax-xmin)*620:.2f},{170-y/ymax*140:.2f}' for x, y in valid)
    return f'<figure><figcaption>{html.escape(label)} · 采样趋势 · 最大 {ymax:.2f}</figcaption><svg viewBox="0 0 700 200" role="img" aria-label="{html.escape(label, quote=True)}"><path d="M40 20 V170 H670" fill="none" stroke="#8ba49b"/><polyline points="{coordinates}" fill="none" stroke="#187a62" stroke-width="2"/><text x="40" y="193" font-size="12">{xmin:.2f}s</text><text x="620" y="193" font-size="12">{xmax:.2f}s</text></svg></figure>'


def report_html(report):
    esc = lambda value: html.escape(str(value if value is not None else '不可用'), quote=True)
    info = report['metadata']
    summary, speed, span = report['summary'], report['speed'], report['range']
    facts = [('视频来源', info.get('video_id')), ('统计段', report['run_id']), ('区间起点 / 结束 / 时长（秒）', ' / '.join(esc(span[key]) for key in ('start', 'end', 'duration'))),
             ('累计过线', summary['cumulative_crossings']), ('机器报警', summary['machine_event_count']), ('观测速度样本均值 / 最小 / 最大 km/h', ' / '.join(esc(speed[key]) for key in ('mean', 'min', 'max'))),
             ('有效速度样本 / 观测样本', ' / '.join(esc(speed[key]) for key in ('speed_samples', 'observed_samples'))), ('速度定义', speed['definition']), ('视频内容身份', info.get('video_identity'))]
    trends = '<h2>交通趋势</h2>' + ''.join(svg_trend(report['trend'], field, label) for field, label in [('flow', '累计过线'), ('vehicle_count', '车辆数量'), ('average_speed', '逐帧平均速度 km/h')])
    lane_html = '<h2>分车道窗口趋势</h2>'
    if not report['lanes']:
        lane_html += '<p>此统计段未保存车道趋势。</p>'
    for lane, points in report['lanes'].items():
        lane_html += '<h3>' + esc(lane) + '</h3><table><tr><th>窗口</th><th>末次过线</th><th>覆盖秒数</th><th>累计过线</th><th>观测均速 km/h</th></tr>'
        for window in (10, 30, 60):
            selected = [p for p in points if p.get('window_seconds') == window]
            if selected:
                last = selected[-1]
                lane_html += '<tr>' + ''.join('<td>' + esc(v) + '</td>' for v in (window, last.get('window_flow'), last.get('covered_seconds'), last.get('cumulative_flow'), last.get('average_speed'))) + '</tr>'
        lane_html += '</table><p>窗口使用 (t−窗口, t]，不足窗口时不外推。</p>'
        for window in (10, 30, 60):
            selected = [p for p in points if p.get('window_seconds') == window]
            lane_html += svg_trend(selected, 'window_flow', f'{window} 秒窗口过线') + svg_trend(selected, 'average_speed', f'{window} 秒采样观测均速 km/h')
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>交通分析报告</title><style>body{font:16px system-ui;margin:2rem;line-height:1.6;color:#182b28}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:.65rem;border:1px solid #b9c9c5;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}@media print{button{display:none}}</style><h1>交通分析报告</h1><button onclick="window.print()">打印 / 保存 PDF</button><table>' + ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v) + '</td></tr>' for k, v in facts) + '</table>' + trends + lane_html + '<h2>机器报警与人工复核</h2><pre>' + esc(json.dumps(summary, ensure_ascii=False, indent=2)) + '</pre><h2>模型、道路与规则配置</h2><pre>' + esc(json.dumps({k: info.get(k) for k in ('calibrated', 'config', 'scene', 'calibration')}, ensure_ascii=False, indent=2)) + '</pre><h2>解释边界</h2>' + ''.join('<p>' + esc(note) + '</p>' for note in report['notes']) + '</html>'
