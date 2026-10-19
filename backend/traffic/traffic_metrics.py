from collections import Counter
from backend.traffic.congestion import CONGESTION_LEVELS, lane_queue, overall_congestion
from backend.traffic.service_level import lane_density, level_of_service


def traffic_metrics(vehicles, seen, flow, timestamp, calibration, lanes, segment_start=0,
                    queue_speed_kmh=10., queue_pixel_speed=5., occupancy=None):
    vehicles = [v for v in vehicles if v.get('type') not in ('person', 'bicycle')]
    calibrated = [v for v in vehicles if v['world'] is not None]
    speeds = [v['speed'] for v in vehicles if v['observed'] and v['speed'] is not None]
    average_speed = sum(speeds)/len(speeds) if speeds else None
    occupancy = occupancy or {}
    lane_stats = []
    for lane in lanes:
        lv = [v for v in vehicles if v['lane'] == lane['name']]
        ls = [v['speed'] for v in lv if v['observed'] and v['speed'] is not None]
        lane_speed = sum(ls)/len(ls) if ls else None
        queue = lane_queue(vehicles, lane['name'], lane.get('direction'), queue_speed_kmh,
                           calibration is not None, queue_pixel_speed)
        density = lane_density(lane, vehicles, calibration)
        los, los_label = level_of_service(density, lane_speed)
        window = flow.lane_window(timestamp, lane['name'], 60, segment_start)
        flow_hour = (window['window_flow']*3600/window['covered_seconds']
                     if window['covered_seconds'] > 0 else None)
        loop = occupancy.get(lane['name'], {})
        lane_stats.append(dict(name=lane['name'], count=len(lv), flow=flow.by_lane[lane['name']],
                               average_speed=lane_speed, density=density, flow_per_hour=flow_hour,
                               occupancy=loop.get('occupancy'), level_of_service=los,
                               service_level_label=los_label, **queue))
    level, level_label = overall_congestion(lane_stats)
    queue_vehicles = sum(lane['queue_vehicles'] for lane in lane_stats)
    queue_length = (sum(lane['queue_length_m'] or 0 for lane in lane_stats)
                    if calibration is not None and lanes else None)
    occupancies = [lane['occupancy'] for lane in lane_stats if lane['occupancy'] is not None]
    overall_density = (len(calibrated)/(calibration.length/1000*len(lanes))
                       if calibration is not None and lanes else None)
    los, los_label = level_of_service(overall_density, average_speed)
    return dict(vehicle_count=len(vehicles), total_vehicles=len(seen),
                average_speed=average_speed,
                max_speed=max(speeds) if speeds else None, min_speed=min(speeds) if speeds else None,
                density=len(calibrated)/(calibration.length/1000) if calibration else None,
                density_estimated=True, density_per_lane=overall_density,
                occupancy=sum(occupancies)/len(occupancies) if occupancies else None,
                level_of_service=los, service_level_label=los_label,
                average_headway=flow.average_headway,
                queue_vehicles=queue_vehicles, queue_length_m=queue_length, queue_estimated=calibration is None,
                congestion_level=level, congestion_label=CONGESTION_LEVELS.get(level),
                vehicle_types=dict(Counter(v['type'] for v in vehicles)), lanes=lane_stats,
                **flow.metrics(timestamp, segment_start))
