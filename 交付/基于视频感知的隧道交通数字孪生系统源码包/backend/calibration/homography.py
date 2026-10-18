import json
import cv2
import numpy as np

TRAVEL_EDGE_12 = '1-2'
TRAVEL_EDGE_23 = '2-3'
TRAVEL_EDGES = (TRAVEL_EDGE_12, TRAVEL_EDGE_23)
# Below this relative difference the two measured edges are treated as equal,
# and scene geometry decides instead of the (noisy) metric comparison.
MEASURED_LENGTH_MARGIN = .02
# A candidate must beat the other by this cosine margin to be used.
ALIGNMENT_MARGIN = .15


def unit(vector):
    vector = np.asarray(vector, float)
    norm = float(np.linalg.norm(vector))
    if norm < 1e-9 or not np.isfinite(norm):
        return np.zeros(2)
    return vector / norm


def normalised_direction(values):
    direction = unit(values)
    if float(np.linalg.norm(direction)) < .5:
        raise ValueError('道路正常行驶方向不能为零')
    return [float(direction[0]), float(direction[1])]


def validate_corner_order(points):
    """Require clockwise order in image coordinates; the first point is TL.

    Sorting by y/x cannot identify the corners of a road that is diagonal in
    the frame, so the supplied order itself defines TL, TR, BR, BL.
    """
    pts = np.asarray(points, float).reshape(4, 2)
    signed_area = float(np.dot(pts[:, 0], np.roll(pts[:, 1], -1)) - np.dot(pts[:, 1], np.roll(pts[:, 0], -1)))
    if signed_area <= 0:
        raise ValueError('四个点必须按左上、右上、右下、左下顺序形成凸四边形，不能交叉或共线')


def _edge_pair_direction(points, edge):
    pts = np.asarray(points, float)
    vectors = (pts[1]-pts[0], pts[2]-pts[3]) if edge == TRAVEL_EDGE_12 else (pts[2]-pts[1], pts[3]-pts[0])
    return unit(sum(unit(vector) for vector in vectors))


def _lane_axis_score(lanes, direction):
    total = weight = 0.
    for lane in lanes:
        pts = np.asarray(lane.get('points', []), float)
        if len(pts) < 2 or not np.isfinite(pts).all():
            continue
        distances = np.linalg.norm(pts[:, None, :]-pts[None, :, :], axis=2)
        first, second = np.unravel_index(np.argmax(distances), distances.shape)
        length = float(distances[first, second])
        if length < 1:
            continue
        axis = unit(pts[second]-pts[first])
        total += length*abs(float(axis@direction))
        weight += length
    return total/weight if weight else None


def _counting_axis_score(counting_line, direction):
    if not isinstance(counting_line, (list, tuple)) or len(counting_line) != 2:
        return None
    line = unit(np.asarray(counting_line[1], float)-np.asarray(counting_line[0], float))
    if float(np.linalg.norm(line)) < .5:
        return None
    return abs(float(np.array([-line[1], line[0]])@direction))


def detect_travel_edge(points, edge_12_m, edge_23_m, scene=None):
    """Return (edge, source) for the calibration edge along the travel direction.

    Rule:
    1. The longer measured edge pair is the road-length / travel pair when the
       two measurements differ by at least 2%. This is orientation independent,
       so portrait, landscape and diagonal camera views behave the same.
    2. If the measurements are nearly equal (square calibration patch), use
       the lane polygons' longest axis when it clearly favours one pair.
    3. Otherwise use the normal of the counting line (travel crosses that line).
    4. If nothing is decisive, keep the legacy edge 2->3 mapping.
    A stored manual override is handled by RoadCalibration and always wins.
    """
    first, second = float(edge_12_m), float(edge_23_m)
    if not (.1 <= first <= 10000 and .1 <= second <= 10000):
        raise ValueError('请输入合理的道路实际宽度和长度')
    if max(first, second)/min(first, second) >= 1+MEASURED_LENGTH_MARGIN:
        return (TRAVEL_EDGE_12 if first > second else TRAVEL_EDGE_23), 'measured_length'
    scene = scene or {}
    directions = {edge: _edge_pair_direction(points, edge) for edge in TRAVEL_EDGES}
    lanes = scene.get('lanes')
    if isinstance(lanes, list) and lanes:
        scores = {edge: _lane_axis_score(lanes, direction) for edge, direction in directions.items()}
        if None not in scores.values() and abs(scores[TRAVEL_EDGE_12]-scores[TRAVEL_EDGE_23]) >= ALIGNMENT_MARGIN:
            return (TRAVEL_EDGE_12 if scores[TRAVEL_EDGE_12] > scores[TRAVEL_EDGE_23] else TRAVEL_EDGE_23), 'lane_alignment'
    counting_line = scene.get('counting_line')
    if counting_line:
        scores = {edge: _counting_axis_score(counting_line, direction) for edge, direction in directions.items()}
        if None not in scores.values() and abs(scores[TRAVEL_EDGE_12]-scores[TRAVEL_EDGE_23]) >= ALIGNMENT_MARGIN:
            return (TRAVEL_EDGE_12 if scores[TRAVEL_EDGE_12] > scores[TRAVEL_EDGE_23] else TRAVEL_EDGE_23), 'counting_line'
    return TRAVEL_EDGE_23, 'default'


class RoadCalibration:
    def __init__(self, payload, scene=None):
        stored_points = np.asarray(payload['points'], float)
        if stored_points.shape != (4, 2) or not np.isfinite(stored_points).all():
            raise ValueError('需要四个有效道路角点')
        self.points = stored_points.astype(np.float32)
        if not cv2.isContourConvex(self.points) or abs(cv2.contourArea(self.points)) < 100:
            raise ValueError('四个点必须按左上、右上、右下、左下顺序形成凸四边形，不能交叉或共线')
        validate_corner_order(self.points)
        self.edge_1_2, self.edge_2_3 = self._measured_edges(payload)
        stored_edge = payload.get('travel_edge')
        mode = payload.get('travel_edge_mode')
        if mode not in ('auto', 'manual'):
            mode = 'manual' if stored_edge in TRAVEL_EDGES else 'auto'
        if mode == 'manual':
            if stored_edge not in TRAVEL_EDGES:
                raise ValueError('手动指定行车方向时必须选择边 1→2 或边 2→3')
            travel_edge, source = stored_edge, 'manual'
        else:
            travel_edge, source = detect_travel_edge(self.points, self.edge_1_2, self.edge_2_3,
                scene if scene is not None else {key: payload.get(key) for key in ('counting_line', 'lanes')})
        # World X is across the road and world Y follows the detected travel
        # direction, so the default legal direction (0, 1) always stays valid.
        self.width, self.length = ((self.edge_2_3, self.edge_1_2) if travel_edge == TRAVEL_EDGE_12
                                   else (self.edge_1_2, self.edge_2_3))
        if not .1 <= self.width <= 1000 or not .1 <= self.length <= 10000:
            raise ValueError('请输入合理的道路实际宽度和长度')
        self.travel_edge, self.travel_edge_mode, self.travel_edge_source = travel_edge, mode, source
        self.travel_direction = np.array([0., 1.])
        target = (np.array([[0, 0], [0, self.length], [self.width, self.length], [self.width, 0]], np.float32)
                  if travel_edge == TRAVEL_EDGE_12
                  else np.array([[0, 0], [self.width, 0], [self.width, self.length], [0, self.length]], np.float32))
        self.matrix = cv2.getPerspectiveTransform(self.points, target)
        if not np.isfinite(self.matrix).all() or abs(np.linalg.det(self.matrix)) < 1e-12:
            raise ValueError('标定矩阵退化，请重新选择角点')
        self.payload = dict(schema_version=2, points=stored_points.tolist(), edge_1_2_m=self.edge_1_2,
                            edge_2_3_m=self.edge_2_3, width_m=self.width, length_m=self.length,
                            travel_edge=travel_edge, travel_edge_mode=mode, travel_edge_source=source)

    @staticmethod
    def _measured_edges(payload):
        first, second = payload.get('edge_1_2_m'), payload.get('edge_2_3_m')
        if first is None and second is None:
            # Legacy payloads stored the two raw edge lengths as width_m / length_m.
            first, second = payload.get('width_m'), payload.get('length_m')
        if first is None or second is None:
            raise ValueError('标定必须同时填写边 1→2 和边 2→3 的实测长度')
        try:
            first, second = float(first), float(second)
        except (TypeError, ValueError) as exc:
            raise ValueError('请输入合理的道路实际宽度和长度') from exc
        if not (.1 <= first <= 10000 and .1 <= second <= 10000):
            raise ValueError('请输入合理的道路实际宽度和长度')
        return first, second

    def contains(self, point):
        return cv2.pointPolygonTest(self.points, tuple(map(float, point)), False) >= 0

    def map(self, point):
        world = cv2.perspectiveTransform(np.array([[point]], np.float32), self.matrix)[0, 0]
        return world.astype(float).tolist()

    def save(self, path):
        path.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path, scene=None):
        return cls(json.loads(path.read_text(encoding='utf-8')), scene=scene) if path.exists() else None
