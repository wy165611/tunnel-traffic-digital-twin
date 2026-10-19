"""Queue and congestion estimates from calibrated per-lane speeds.

Queue counts use the same calibrated speed stream as other speed features, so
they are unavailable without a real road-scale calibration. Queue length is
the projected span of queued vehicle centres, not a measured physical queue.
"""
import numpy as np

CONGESTION_LEVELS = {'free': '畅通', 'slow': '缓行', 'congested': '拥堵', 'severe': '严重拥堵'}
LEVEL_ORDER = list(CONGESTION_LEVELS)


def congestion_level(queue_ratio, average_speed):
    if queue_ratio is None or average_speed is None:
        return None
    if queue_ratio >= .75 or average_speed < 5:
        return 'severe'
    if queue_ratio >= .5 or average_speed < 15:
        return 'congested'
    if queue_ratio >= .25 or average_speed < 30:
        return 'slow'
    return 'free'


def lane_queue(vehicles, lane_name, direction, speed_threshold, calibrated):
    lane_vehicles = [v for v in vehicles if v.get('lane') == lane_name and v.get('observed')]
    if not calibrated:
        return dict(queue_vehicles=None, queue_length_m=None, queue_ratio=None,
                    congestion_level=None, congestion_label=None)
    speeds = [v['speed'] for v in lane_vehicles if v.get('speed') is not None]
    queue = [v for v in lane_vehicles if v.get('speed') is not None and v['speed'] < speed_threshold]
    average_speed = sum(speeds)/len(speeds) if speeds else None
    ratio = len(queue)/len(lane_vehicles) if lane_vehicles else None
    length = None
    axis = np.asarray(direction or [0, 1], float)
    if float(np.linalg.norm(axis)) >= .1 and len(queue) >= 2 and all(v.get('world') is not None for v in queue):
        axis = axis/np.linalg.norm(axis)
        projections = [float(np.asarray(v['world'], float)@axis) for v in queue]
        length = max(projections)-min(projections)
    level = congestion_level(ratio, average_speed)
    return dict(queue_vehicles=len(queue), queue_length_m=length, queue_ratio=ratio,
                congestion_level=level, congestion_label=CONGESTION_LEVELS.get(level))


def overall_congestion(lanes):
    levels = [lane['congestion_level'] for lane in lanes if lane.get('congestion_level')]
    if not levels:
        return None, None
    level = max(levels, key=LEVEL_ORDER.index)
    return level, CONGESTION_LEVELS[level]
