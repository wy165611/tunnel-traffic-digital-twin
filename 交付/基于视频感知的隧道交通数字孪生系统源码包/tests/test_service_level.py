import csv
import json
import cv2
import numpy as np
import pytest
from backend.calibration.homography import RoadCalibration
from backend.exporter import FIELDS
from backend.reports import build_report, report_html
from backend.traffic.flow_counter import FlowCounter
from backend.traffic.service_level import LoopOccupancy, automatic_loop, level_of_service, scene_loops
from backend.traffic.traffic_metrics import traffic_metrics
from test_api import client

LANE = dict(name='Lane 1', points=[[20, 0], [80, 0], [80, 200], [20, 200]], direction=[0, 1])


def vehicle(t=1, pixel=(50, 100), lane='Lane 1', speed=30, world=(5, 50), vid=1, observed=True):
    return dict(id=vid, timestamp=t, pixel=list(pixel), lane=lane, speed=speed, world=list(world),
                observed=observed, type='car', lane_direction=[0, 1])


def test_automatic_loop_is_inside_lane_and_configurable():
    loop = automatic_loop(LANE)
    assert len(loop) == 4
    polygon = np.asarray(LANE['points'], np.float32)
    for point in loop:
        assert cv2.pointPolygonTest(polygon, tuple(point), False) >= 0
    assert scene_loops([LANE])[0]['lane'] == 'Lane 1'
    manual = dict(LANE, loop=[[30, 80], [70, 80], [70, 120], [30, 120]])
    assert scene_loops([manual])[0]['points'] == manual['loop']


def test_loop_occupancy_accumulates_observed_time_and_respects_toggle():
    tracker = LoopOccupancy([LANE], enabled=True)
    assert tracker.update(0, [])['Lane 1']['occupancy'] is None
    assert tracker.update(1, [vehicle(pixel=(50, 100))])['Lane 1']['occupancy'] == pytest.approx(100)
    assert tracker.update(2, [vehicle(pixel=(50, 100))])['Lane 1']['occupancy'] == pytest.approx(100)
    outside = tracker.update(3, [vehicle(pixel=(10, 10))])['Lane 1']
    assert outside['occupancy'] == pytest.approx(200/3)
    final = tracker.update(4, [])['Lane 1']
    assert final['occupancy'] == pytest.approx(50)
    assert final['covered_seconds'] == 4
    assert LoopOccupancy([LANE], enabled=False).update(1, [vehicle()]) == {}


def test_level_of_service_density_bands_and_speed_downgrade():
    assert level_of_service(5, 80) == ('A', '自由流')
    assert level_of_service(10, 80)[0] == 'B'
    assert level_of_service(20, 80)[0] == 'D'
    assert level_of_service(35, 80)[0] == 'F'
    assert level_of_service(5, 20)[0] == 'D'
    assert level_of_service(5, 10)[0] == 'E'
    assert level_of_service(None, 80) == (None, None)


def test_occupancy_and_los_flow_into_metrics_and_exports(client):
    c, s = client
    geometry = dict(points=[[20, 0], [80, 0], [80, 200], [20, 200]], edge_1_2_m=10, edge_2_3_m=200,
                    lanes=[dict(**LANE, solid_line=True)], speed_limit_kmh=60)
    state = c.post('/api/calibration', json=geometry)
    assert state.status_code == 200
    body = state.json()
    assert len(body['scene']['virtual_loops']) == 1 and len(body['scene']['virtual_loops'][0]['points']) == 4
    assert body['settings']['occupancy_enabled'] is True
    assert c.post('/api/settings', json={'occupancy_enabled': False}).json()['settings']['occupancy_enabled'] is False
    assert c.post('/api/settings', json={'occupancy_enabled': True}).status_code == 200
    calibration = RoadCalibration(dict(points=geometry['points'], edge_1_2_m=10, edge_2_3_m=200))
    loop = {'Lane 1': dict(occupancy=25.0)}
    metrics = traffic_metrics([vehicle()], {1}, FlowCounter(), 1, calibration, [LANE], 0, occupancy=loop)
    assert metrics['lanes'][0]['occupancy'] == 25
    assert metrics['lanes'][0]['level_of_service'] in ('A', 'B', 'C', 'D', 'E', 'F')
    assert metrics['level_of_service'] is not None and metrics['occupancy'] == 25
    assert 'occupancy' in FIELDS['traffic_statistics'] and 'level_of_service' in FIELDS['lane_statistics']
    assert c.post('/api/calibration', json=dict(geometry, lanes=[dict(**LANE, loop=[[1, 1], [1, 1], [1, 1]])])).status_code == 422


def test_report_includes_service_level_fields(tmp_path):
    with (tmp_path / 'traffic_statistics.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['timestamp', 'flow', 'vehicle_count', 'occupancy', 'level_of_service',
                                                    'service_level_label', 'queue_vehicles', 'queue_length_m'])
        writer.writeheader()
        writer.writerow(dict(timestamp=1, flow=2, vehicle_count=1, occupancy=25, level_of_service='C',
                             service_level_label='稳定流', queue_vehicles=1, queue_length_m=12))
    (tmp_path / 'run.json').write_text(json.dumps(dict(segment_start=0)))
    report = build_report(tmp_path, 'run')
    assert report['service_level']['occupancy'] == 25 and report['service_level']['level_of_service'] == 'C'
    html = report_html(report)
    assert '时间占有率 / 服务水平' in html and '25' in html


def test_processor_exports_occupancy_and_level_of_service_rows():
    from backend.processor import TrafficProcessor
    from backend.settings import load_config

    class Reader:
        width = height = 200
        display_width = display_height = 200
        fps = 10
        index = 0
        def read(self):
            i = self.index; self.index += 1
            return (i, i/10, np.zeros((200, 200, 3), np.uint8)) if i < 20 else None

    class Detector:
        device = 'cpu'; detect_ms = 1.
        def __init__(self): self.i = 0
        def detect(self, frame):
            y = 30+self.i*3; self.i += 1
            return [dict(box=np.array([90, y, 110, y+20], float), type='car', confidence=.95)]

    calibration = RoadCalibration(dict(points=[[20, 20], [180, 20], [180, 180], [20, 180]],
                                       edge_1_2_m=10, edge_2_3_m=100))
    lane = dict(name='Lane 1', points=[[40, 20], [160, 20], [160, 180], [40, 180]], direction=[0, 1], solid_line=True)
    config = load_config(); config['video']['detection_interval'] = 1
    processor = TrafficProcessor(Reader(), Detector(), config, dict(lanes=[lane], counting_line=None), calibration)
    while processor.step() is not None:
        pass
    processor.close()
    with (processor.exporter.directory / 'lane_statistics.csv').open(encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    assert rows and rows[-1]['occupancy'] != '' and rows[-1]['level_of_service'] in list('ABCDEF')
    with (processor.exporter.directory / 'traffic_statistics.csv').open(encoding='utf-8-sig') as stream:
        stats = list(csv.DictReader(stream))
    assert stats and stats[-1]['occupancy'] != '' and stats[-1]['level_of_service'] in list('ABCDEF')
