import json
import cv2
import numpy as np


class RoadCalibration:
    def __init__(self, payload):
        self.payload = {name: payload[name] for name in ('points', 'width_m', 'length_m')}
        self.points = np.asarray(payload['points'], np.float32)
        self.width = float(payload['width_m'])
        self.length = float(payload['length_m'])
        if self.points.shape != (4, 2) or not np.isfinite(self.points).all():
            raise ValueError('需要四个有效道路角点')
        if not .1 <= self.width <= 1000 or not .1 <= self.length <= 10000:
            raise ValueError('请输入合理的道路实际宽度和长度')
        if not cv2.isContourConvex(self.points) or abs(cv2.contourArea(self.points)) < 100:
            raise ValueError('四个点必须按左上、右上、右下、左下顺序形成凸四边形，不能交叉或共线')
        target = np.array([[0, 0], [self.width, 0], [self.width, self.length], [0, self.length]], np.float32)
        self.matrix = cv2.getPerspectiveTransform(self.points, target)
        if not np.isfinite(self.matrix).all() or abs(np.linalg.det(self.matrix)) < 1e-12:
            raise ValueError('标定矩阵退化，请重新选择角点')

    def contains(self, point):
        return cv2.pointPolygonTest(self.points, tuple(map(float, point)), False) >= 0

    def map(self, point):
        world = cv2.perspectiveTransform(np.array([[point]], np.float32), self.matrix)[0, 0]
        return world.astype(float).tolist()

    def save(self, path):
        path.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path):
        return cls(json.loads(path.read_text(encoding='utf-8'))) if path.exists() else None
