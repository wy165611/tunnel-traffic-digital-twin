from backend.traffic.flow_counter import FlowCounter
from backend.traffic.traffic_metrics import traffic_metrics

LANES = [dict(name='L1', points=[[0, 0], [10, 0], [10, 10], [0, 10]], direction=[0, 1])]


class Calibration:
    length = 100.

    def map(self, point):
        return [float(point[0]), float(point[1])]


def vehicle(vid, observed, world=(1., 1.)):
    return dict(id=vid, type='car', world=list(world), observed=observed, speed=50. if observed else None,
                lane='L1', pixel_speed=1.)


def test_lane_flow_rate_is_not_extrapolated_from_a_few_seconds():
    flow = FlowCounter([[0, 5], [10, 5]])
    flow.update(1, [5, 4], 0., 'car', 'L1')
    flow.update(1, [5, 6], .5, 'car', 'L1')
    lane = traffic_metrics([], {1}, flow, .5, None, LANES)['lanes'][0]
    assert lane['flow_per_hour'] is None and lane['flow_per_hour_estimated'] is True


def test_density_ignores_kalman_predicted_tracks():
    flow = FlowCounter(None)
    metrics = traffic_metrics([vehicle(1, True), vehicle(2, False), vehicle(3, False)], {1, 2, 3},
                              flow, 1., Calibration(), LANES)
    assert metrics['density'] == 10.

