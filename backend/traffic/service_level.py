"""Virtual loops, time occupancy and an engineering A-F level of service."""
import cv2
import numpy as np

LOS_LABELS = {'A': '自由流', 'B': '基本自由流', 'C': '稳定流', 'D': '接近不稳定', 'E': '不稳定', 'F': '强制流'}
LOS_LIMITS = [('A', 7.), ('B', 11.), ('C', 16.), ('D', 22.), ('E', 28.), ('F', float('inf'))]
LEVEL_ORDER = [name for name, _ in LOS_LIMITS]


def automatic_loop(lane):
    """A thin inscribed loop aligned with the lane's minimum-area rectangle."""
    points = np.asarray(lane.get('points') or [], float)
    if len(points) < 3 or not np.isfinite(points).all():
        return None
    box = cv2.boxPoints(cv2.minAreaRect(points.astype(np.float32))).astype(float)
    center = box.mean(axis=0)
    edges = [box[1]-box[0], box[2]-box[1]]
    long_edge = edges[0] if np.linalg.norm(edges[0]) >= np.linalg.norm(edges[1]) else edges[1]
    long_length = float(np.linalg.norm(long_edge))
    short_length = float(np.linalg.norm(edges[0] if long_edge is edges[1] else edges[1]))
    if long_length < 2 or short_length < 1:
        return None
    axis = long_edge/long_length
    across = np.array([-axis[1], axis[0]])
    half_long, half_wide = max(2., long_length*.18), max(1.5, short_length*.55)
    corners = [(center+axis*half_long*sx+across*half_wide*sy).tolist()
               for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    polygon = points.astype(np.float32)
    if all(cv2.pointPolygonTest(polygon, tuple(corner), False) >= 0 for corner in corners):
        return corners
    # Irregular convex lanes: an inset copy of the polygon always stays inside.
    return (center+(points-center)*.45).tolist()


def scene_loops(lanes):
    loops = []
    for lane in lanes or []:
        points = lane.get('loop') or automatic_loop(lane)
        if points:
            loops.append(dict(lane=lane['name'], points=points))
    return loops


class LoopOccupancy:
    """Cumulative share of observed video time each loop polygon is occupied."""

    def __init__(self, lanes, enabled=True):
        self.enabled = enabled
        self.loops = {item['lane']: np.asarray(item['points'], np.float32) for item in scene_loops(lanes)}
        self.stats = {name: dict(occupied_seconds=0., covered_seconds=0., last_timestamp=None, occupied=False)
                      for name in self.loops}

    def update(self, timestamp, vehicles):
        if not self.enabled:
            return {}
        occupied_now = set()
        for vehicle in vehicles:
            name = vehicle.get('lane')
            polygon = self.loops.get(name)
            if polygon is None or not vehicle.get('observed') or vehicle.get('pixel') is None:
                continue
            if cv2.pointPolygonTest(polygon, tuple(map(float, vehicle['pixel'])), False) >= 0:
                occupied_now.add(name)
        result = {}
        for name, state in self.stats.items():
            previous = state['last_timestamp']
            occupied = name in occupied_now
            if previous is not None and timestamp > previous:
                elapsed = timestamp-previous
                state['covered_seconds'] += elapsed
                if occupied:
                    state['occupied_seconds'] += elapsed
            state['last_timestamp'] = timestamp
            state['occupied'] = occupied
            covered = state['covered_seconds']
            result[name] = dict(
                occupancy=100.*state['occupied_seconds']/covered if covered > 0 else None,
                occupied_seconds=state['occupied_seconds'], covered_seconds=covered)
        return result


def lane_length_m(lane, calibration):
    if calibration is None:
        return None
    axis = np.asarray(lane.get('direction') or [0, 1], float)
    if float(np.linalg.norm(axis)) < .1:
        return None
    axis /= np.linalg.norm(axis)
    projections = [float(np.asarray(calibration.map(point), float)@axis) for point in lane.get('points', [])]
    if not projections:
        return None
    length = max(projections)-min(projections)
    return length if length >= 1 else None


def lane_density(lane, vehicles, calibration):
    length = lane_length_m(lane, calibration)
    if length is None:
        return None
    count = sum(1 for vehicle in vehicles
                if vehicle.get('lane') == lane['name'] and vehicle.get('observed') and vehicle.get('world') is not None)
    return count/(length/1000.)


def level_of_service(density, speed):
    """HCM-like density bands, degraded by low observed speed."""
    if density is None:
        return None, None
    index = next(index for index, (_, limit) in enumerate(LOS_LIMITS) if density <= limit)
    if speed is not None:
        if speed < 15:
            index = max(index, LEVEL_ORDER.index('E'))
        elif speed < 30:
            index = max(index, LEVEL_ORDER.index('D'))
    name = LEVEL_ORDER[index]
    return name, LOS_LABELS[name]
