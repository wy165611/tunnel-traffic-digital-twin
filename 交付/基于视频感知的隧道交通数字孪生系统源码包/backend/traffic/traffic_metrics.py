from collections import Counter


def traffic_metrics(vehicles, seen, flow, timestamp, calibration, lanes, segment_start=0):
    calibrated = [v for v in vehicles if v['world'] is not None]
    speeds = [v['speed'] for v in vehicles if v['speed'] is not None]
    lane_stats = []
    for lane in lanes:
        lv = [v for v in vehicles if v['lane'] == lane['name']]
        ls = [v['speed'] for v in lv if v['speed'] is not None]
        lane_stats.append(dict(name=lane['name'], count=len(lv), flow=flow.by_lane[lane['name']],
                               average_speed=sum(ls)/len(ls) if ls else None))
    return dict(vehicle_count=len(vehicles), total_vehicles=len(seen),
                average_speed=sum(speeds)/len(speeds) if speeds else None,
                max_speed=max(speeds) if speeds else None, min_speed=min(speeds) if speeds else None,
                density=len(calibrated)/(calibration.length/1000) if calibration else None,
                density_estimated=True, occupancy=None,
                average_headway=flow.average_headway,
                vehicle_types=dict(Counter(v['type'] for v in vehicles)), lanes=lane_stats,
                **flow.metrics(timestamp, segment_start))
