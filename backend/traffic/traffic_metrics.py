from collections import Counter
from backend.traffic.congestion import CONGESTION_LEVELS, lane_queue, overall_congestion


def traffic_metrics(vehicles, seen, flow, timestamp, calibration, lanes, segment_start=0, queue_speed_kmh=10.):
    vehicles = [v for v in vehicles if v.get('type') not in ('person', 'bicycle')]
    calibrated = [v for v in vehicles if v['world'] is not None]
    speeds = [v['speed'] for v in vehicles if v['observed'] and v['speed'] is not None]
    lane_stats = []
    for lane in lanes:
        lv = [v for v in vehicles if v['lane'] == lane['name']]
        ls = [v['speed'] for v in lv if v['observed'] and v['speed'] is not None]
        queue = lane_queue(vehicles, lane['name'], lane.get('direction'), queue_speed_kmh, calibration is not None)
        lane_stats.append(dict(name=lane['name'], count=len(lv), flow=flow.by_lane[lane['name']],
                               average_speed=sum(ls)/len(ls) if ls else None, **queue))
    level, level_label = overall_congestion(lane_stats)
    queue_vehicles = sum(lane['queue_vehicles'] for lane in lane_stats) if calibration is not None else None
    queue_length = (sum(lane['queue_length_m'] or 0 for lane in lane_stats)
                    if calibration is not None and lanes else None)
    return dict(vehicle_count=len(vehicles), total_vehicles=len(seen),
                average_speed=sum(speeds)/len(speeds) if speeds else None,
                max_speed=max(speeds) if speeds else None, min_speed=min(speeds) if speeds else None,
                density=len(calibrated)/(calibration.length/1000) if calibration else None,
                density_estimated=True, occupancy=None,
                average_headway=flow.average_headway,
                queue_vehicles=queue_vehicles, queue_length_m=queue_length,
                congestion_level=level, congestion_label=CONGESTION_LEVELS.get(level),
                vehicle_types=dict(Counter(v['type'] for v in vehicles)), lanes=lane_stats,
                **flow.metrics(timestamp, segment_start))
