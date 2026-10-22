import copy
import pytest
from backend.events.rules import EventDetector, EVENT_NAMES
from backend.settings import load_config
from backend.traffic.congestion import lane_queue, overall_congestion
from backend.traffic.traffic_metrics import traffic_metrics
from backend.traffic.flow_counter import FlowCounter
from backend.vision.detector import model_supports_intrusion
from test_api import client


def vehicle(t, speed=0, lane='Lane 1', world=None, kind='car', direction=(0, 1), vid=1, path=None,
            lane_solid=True, pixel_speed=None):
    return dict(id=vid, timestamp=t, speed=speed, lane=lane, type=kind, observed=True,
                world=world, lane_direction=list(direction), world_trajectory=path or [],
                lane_solid=lane_solid, pixel_speed=pixel_speed)


def detector(**changes):
    config = copy.deepcopy(load_config()['events'])
    config.update(changes)
    return EventDetector(config)


def test_speeding_and_slow_speed_require_speed_and_respect_switches():
    events = detector(cooldown_seconds=0, speeding_kmh=80, slow_speed_kmh=20)
    assert [e['event'] for e in events.update(vehicle(1, 90), [0, 1])] == ['SPEEDING']
    assert [e['event'] for e in events.update(vehicle(1, 92), [0, 1])] == ['SPEEDING']
    assert any(e['event'] == 'SLOW SPEED' for e in events.update(vehicle(2, 12, vid=2), [0, 1]))
    assert not events.update(vehicle(3, None, vid=3), [0, 1])
    off = detector(speeding_enabled=False, slow_speed_enabled=False, cooldown_seconds=0)
    assert not off.update(vehicle(1, 120, vid=11), [0, 1])
    assert not [e for e in off.update(vehicle(2, 12, vid=12), [0, 1]) if e['event'] in ('SPEEDING', 'SLOW SPEED')]
    assert EVENT_NAMES['SPEEDING'] == '超速' and EVENT_NAMES['SLOW SPEED'] == '低速行驶'


def test_illegal_lane_change_needs_sustained_new_lane():
    events = detector(lane_change_seconds=1.0, cooldown_seconds=0)
    assert not events.update(vehicle(0, 30, 'A'), [0, 1])
    assert not events.update(vehicle(1.5, 30, 'B'), [0, 1])
    assert not events.update(vehicle(2.0, 30, 'B'), [0, 1])
    assert [e['event'] for e in events.update(vehicle(2.5, 30, 'B'), [0, 1])] == ['ILLEGAL LANE CHANGE']
    assert not events.update(vehicle(10, 30, 'B'), [0, 1])  # reported once per change
    assert not events.update(vehicle(11, 30, 'A'), [0, 1])
    assert [e['event'] for e in events.update(vehicle(13, 30, 'A'), [0, 1])] == ['ILLEGAL LANE CHANGE']
    off = detector(lane_change_enabled=False, lane_change_seconds=.5)
    assert not off.update(vehicle(0, 30, 'A'), [0, 1])
    assert not off.update(vehicle(1, 30, 'B'), [0, 1])
    assert not off.update(vehicle(2, 30, 'B'), [0, 1])


def test_close_following_uses_time_headway_in_same_lane():
    events = detector(tailgating_headway_seconds=2.0, cooldown_seconds=0)
    ego = vehicle(1, 36, world=[0, 10])
    leader = vehicle(1, 30, world=[0, 25], vid=2)
    traffic = [ego, leader]
    assert [e['event'] for e in events.update(ego, [0, 1], traffic)] == ['CLOSE FOLLOWING']
    far = [ego, vehicle(1, 30, world=[0, 50], vid=3)]
    assert not events.update(ego, [0, 1], far)
    behind = [ego, vehicle(1, 30, world=[0, 0], vid=4)]
    assert not events.update(ego, [0, 1], behind)
    assert not events.update(vehicle(1, None, world=[0, 10], vid=9), [0, 1], far)
    off = detector(tailgating_enabled=False, tailgating_headway_seconds=2.0)
    assert not off.update(ego, [0, 1], traffic)


def test_pedestrian_and_bicycle_intrusion_only_for_supported_types():
    events = detector(cooldown_seconds=0, intrusion_enabled=True)
    pedestrian = vehicle(1, None, kind='person', vid=5)
    bicycle = vehicle(1, None, kind='bicycle', vid=6)
    assert [e['event'] for e in events.update(pedestrian, [0, 1])] == ['PEDESTRIAN INTRUSION']
    assert [e['event'] for e in events.update(bicycle, [0, 1])] == ['NON MOTOR INTRUSION']
    assert not [e for e in events.update(vehicle(1, 90, vid=7), [0, 1]) if 'INTRUSION' in e['event']]
    assert not events.update(vehicle(1, None, kind='car', vid=8), [0, 1])
    off = detector(intrusion_enabled=False)
    assert not off.update(pedestrian, [0, 1])
    assert model_supports_intrusion('coco_yolo11n')
    assert model_supports_intrusion('ssdlite320_mobilenet_v3_large')
    assert not model_supports_intrusion('visdrone_yolo11n')


def test_person_is_not_scored_as_speeding_even_when_speed_exists():
    events = detector(cooldown_seconds=0, intrusion_enabled=True)
    person = vehicle(1, 120, kind='person', vid=11)
    assert [e['event'] for e in events.update(person, [0, 1])] == ['PEDESTRIAN INTRUSION']


def test_dashed_lane_change_is_allowed_and_speed_limit_overrides_threshold():
    events = detector(lane_change_seconds=.5, cooldown_seconds=0)
    assert not events.update(vehicle(0, 30, 'A'), [0, 1])
    assert not events.update(vehicle(1, 30, 'B', lane_solid=False), [0, 1])
    assert not events.update(vehicle(2, 30, 'B', lane_solid=False), [0, 1])
    limit = detector(cooldown_seconds=0, speeding_kmh=80)
    assert [e['event'] for e in limit.update(vehicle(1, 65), [0, 1], speed_limit=60)] == ['SPEEDING']
    assert not limit.update(vehicle(2, 55, vid=2), [0, 1], speed_limit=60)


def test_scene_carries_speed_limit_and_solid_lines_into_camera_template(client):
    c, s = client
    lane = dict(name='Lane 1', points=[[40, 0], [160, 0], [160, 400], [40, 400]], direction=[0, 1], solid_line=False)
    geometry = dict(points=[[40, 0], [160, 0], [160, 400], [40, 400]], width_m=12, length_m=40,
                    speed_limit_kmh=60, lanes=[lane])
    state = c.post('/api/calibration', json=geometry).json()
    assert state['scene']['speed_limit_kmh'] == 60 and state['scene']['lanes'][0]['solid_line'] is False
    saved = c.post('/api/camera-templates', json=dict(video_token=s.video_token, scene_revision=s.scene_revision,
                                                      name='限速机位', note='')).json()
    assert saved['scene']['speed_limit_kmh'] == 60 and saved['scene']['lanes'][0]['solid_line'] is False
    assert c.post('/api/calibration', json=dict(geometry, speed_limit_kmh=1)).status_code == 422


def test_lane_queue_needs_calibration_and_reports_span():
    states = [vehicle(1, speed, world=[0, y], vid=index+1, pixel_speed=pixel)
              for index, (speed, y, pixel) in enumerate([(5, 10, 2), (5, 14, 2), (40, 30, 30)])]
    calibrated = lane_queue(states, 'Lane 1', [0, 1], 10, True)
    assert calibrated['queue_vehicles'] == 2
    assert calibrated['queue_length_m'] == pytest.approx(4)
    assert not calibrated['queue_estimated']
    assert calibrated['congestion_level'] == 'congested' and calibrated['congestion_label'] == '拥堵'
    estimated = lane_queue(states, 'Lane 1', [0, 1], 10, False)
    assert estimated['queue_vehicles'] == 2 and estimated['queue_length_m'] is None
    assert estimated['queue_estimated'] and estimated['congestion_label'] is not None
    assert overall_congestion([calibrated]) == ('congested', '拥堵')


def test_traffic_metrics_exposes_queue_and_congestion_without_counting_persons():
    lanes = [dict(name='Lane 1', points=[[0, 0], [10, 0], [10, 100], [0, 100]], direction=[0, 1])]
    calibration = __import__('backend.calibration.homography', fromlist=['RoadCalibration']).RoadCalibration(
        dict(points=[[0, 0], [10, 0], [10, 100], [0, 100]], width_m=10, length_m=100))
    states = [vehicle(1, 5, world=[0, 10], vid=1, pixel_speed=1), vehicle(1, 40, world=[0, 40], vid=2, pixel_speed=30),
              vehicle(1, None, kind='person', world=[0, 20], vid=3)]
    metrics = traffic_metrics(states, {1, 2, 3}, FlowCounter(), 1, calibration, lanes, 0, 10)
    assert metrics['vehicle_count'] == 2
    assert metrics['queue_vehicles'] == 1 and metrics['congestion_label'] is not None
    assert metrics['lanes'][0]['queue_vehicles'] == 1
    uncalibrated = traffic_metrics(states, {1}, FlowCounter(), 1, None, lanes, 0, 10)
    assert uncalibrated['queue_vehicles'] == 1 and uncalibrated['queue_estimated']
    assert uncalibrated['queue_length_m'] is None


def test_settings_api_exposes_thresholds_and_model_support(client):
    c, s = client
    state = c.get('/api/state').json()
    assert state['settings']['speeding_kmh'] == 80
    assert state['settings']['intrusion_supported'] is False
    assert state['settings']['intrusion_enabled'] is False
    response = c.post('/api/settings', json={'speeding_kmh': 90, 'slow_speed_kmh': 15, 'lane_change_enabled': False,
                                             'tailgating_headway_seconds': 1.5, 'queue_speed_kmh': 8, 'model': 'coco_yolo11n'})
    assert response.status_code == 200
    settings = response.json()['settings']
    assert settings['speeding_kmh'] == 90 and settings['lane_change_enabled'] is False
    assert settings['intrusion_supported'] is True
    assert c.post('/api/settings', json={'speeding_kmh': 10, 'slow_speed_kmh': 20}).status_code == 422
