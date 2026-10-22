from backend.events.rules import EventDetector
from backend.traffic.traffic_metrics import traffic_metrics
from test_api import client


def vehicle(speed=120., lane='Lane 1', timestamp=10.):
    return dict(id=1, type='car', timestamp=timestamp, speed=speed, lane=lane,
                lane_direction=[0, 1], lane_solid=True, pixel=[50, 90],
                world=[6., 20.], world_trajectory=[dict(timestamp=timestamp-.5, point=[6., 10.]),
                                                   dict(timestamp=timestamp, point=[6., 20.])],
                pixel_speed=100., observed=True)


CONFIG = dict(stop_speed=3., stop_seconds=3., speeding_enabled=True, speeding_kmh=80.,
              slow_speed_enabled=True, slow_speed_kmh=20., lane_change_enabled=True,
              lane_change_seconds=1., tailgating_enabled=True, tailgating_headway_seconds=2.,
              wrong_way_seconds=1., wrong_way_cosine=-.6, hard_braking_acceleration=-4.,
              cooldown_seconds=5., queue_speed_kmh=10.)


def test_calibration_gate_silences_the_speed_headway_queue_group():
    events = EventDetector(CONFIG, calibration_available=False).update(vehicle(), [0, 1], [vehicle()])
    assert events == []
    enabled = EventDetector(CONFIG, calibration_available=True).update(vehicle(), [0, 1], [vehicle()])
    assert [event['event'] for event in enabled] == ['SPEEDING']


def test_metrics_without_calibration_keep_queue_metres_and_density_unavailable():
    class Flow:
        by_lane = {'Lane 1': 0}
        average_headway = None
        def lane_window(self, *args): return dict(window_flow=0, covered_seconds=5.)
        def metrics(self, *args): return dict(total_flow=0, flow_per_min=0., flow_per_hour=0., flow_estimated=True)
    lanes = [dict(name='Lane 1', points=[[0, 0], [10, 0], [10, 20], [0, 20]], direction=[0, 1])]
    metrics = traffic_metrics([vehicle()], {1}, Flow(), 10., None, lanes, queue_pixel_speed=1000.)
    assert metrics['queue_length_m'] is None
    assert metrics['density'] is None and metrics['density_per_lane'] is None
    assert metrics['level_of_service'] is None and metrics['queue_estimated'] is True


def test_state_exposes_calibration_gate_and_clears_it_after_saving(client):
    c, _ = client
    state = c.get('/api/state').json()
    assert state['settings']['calibration_available'] is False
    assert 'queue_length_m' in state['settings']['calibration_required_metrics']
    geometry = dict(points=[[40, 0], [160, 0], [160, 400], [40, 400]], edge_1_2_m=12, edge_2_3_m=40,
                    travel_edge_mode='auto', counting_line=[[40, 65], [160, 65]], counting_line_mode='manual',
                    lanes=[dict(name='Lane 1', points=[[40, 0], [160, 0], [160, 400], [40, 400]], direction=[0, 1])])
    assert c.post('/api/calibration', json=geometry).status_code == 200
    assert c.get('/api/state').json()['settings']['calibration_available'] is True


def test_resolution_change_invalidates_saved_calibration_until_resaved(client):
    c, service = client
    geometry = dict(points=[[40, 0], [160, 0], [160, 400], [40, 400]], edge_1_2_m=12, edge_2_3_m=40,
                    travel_edge_mode='auto', counting_line=[[40, 65], [160, 65]], counting_line_mode='manual',
                    lanes=[dict(name='Lane 1', points=[[40, 0], [160, 0], [160, 400], [40, 400]], direction=[0, 1])])
    assert c.post('/api/calibration', json=geometry).status_code == 200
    service.reader.resolution_changed = True
    service.reader.resolution_change = dict(previous=[200, 400], current=[400, 800])
    service.changed()
    state = service.state()
    notice = state['calibration_notice']
    assert notice['reason'] == 'resolution_changed' and notice['previous'] == [200, 400]
    assert '重新标定' in notice['message'] and state['settings']['calibration_available'] is False
    assert state['calibration']['points']  # 保留已存标定，便于重新绘制或确认
    service.reset_processor_sync(0)
    assert service.processor.calibration is None
    assert service.processor.events.calibration_available is False
    assert c.post('/api/calibration', json=geometry).status_code == 200
    cleared = service.state()
    assert cleared['calibration_notice'] is None and cleared['settings']['calibration_available'] is True
