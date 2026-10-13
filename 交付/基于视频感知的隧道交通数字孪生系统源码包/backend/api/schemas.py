from typing import Literal
import math
from pydantic import BaseModel, Field, model_validator

Point = tuple[float, float]


class LaneInput(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    points: list[Point] = Field(min_length=3, max_length=50)
    direction: Point = (0, 1)


class SceneInput(BaseModel):
    video_token: str | None = None
    scene_revision: int | None = Field(default=None, ge=0)
    points: list[Point] | None = Field(default=None, min_length=4, max_length=4)
    width_m: float | None = Field(default=None, ge=.1, le=1000)
    length_m: float | None = Field(default=None, ge=.1, le=10000)
    counting_line: list[Point] | None = Field(default=None, min_length=2, max_length=2)
    counting_line_mode: Literal['auto', 'manual', 'disabled'] | None = None
    lanes: list[LaneInput] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def validate_geometry(self):
        import cv2
        import numpy as np
        if len({x.name for x in self.lanes}) != len(self.lanes):
            raise ValueError('车道名称不能重复')
        points = list(self.points or []) + list(self.counting_line or [])
        for lane in self.lanes:
            points.extend(lane.points)
            if not all(math.isfinite(x) for x in lane.direction) or math.hypot(*lane.direction) < .001:
                raise ValueError('车道行驶方向不能为零')
            contour = np.array(lane.points, np.float32)
            if not cv2.isContourConvex(contour) or abs(cv2.contourArea(contour)) < 1:
                raise ValueError('车道需要按边界顺序绘制凸多边形')
        if not all(math.isfinite(x) for p in points for x in p):
            raise ValueError('坐标必须为有限值')
        if self.counting_line and math.dist(*self.counting_line) < 1:
            raise ValueError('计数线的两个端点不能重合')
        if self.counting_line_mode == 'manual' and self.counting_line is None:
            raise ValueError('手动计数模式需要绘制计数线')
        if self.points and (self.width_m is None or self.length_m is None):
            raise ValueError('标定必须填写实际长度和宽度')
        return self


class VideoSelection(BaseModel):
    video_id: str


class PathImport(BaseModel):
    path: str


class PlaybackControl(BaseModel):
    action: Literal['play', 'pause', 'restart', 'seek', 'rate']
    seconds: float = Field(default=0, ge=0, allow_inf_nan=False)
    rate: Literal[0.5, 1., 2.] = 1.


class RuntimeSettings(BaseModel):
    video_token: str | None = None
    model: Literal['visdrone_yolo11n', 'coco_yolo11n', 'ssdlite320_mobilenet_v3_large'] = 'visdrone_yolo11n'
    confidence: float = Field(default=.4, ge=.1, le=.95)
    detection_interval: int = Field(default=2, ge=1, le=10)
    smoothing_frames: int = Field(default=10, ge=5, le=30)
    stop_speed: float = Field(default=3, ge=0, le=20)
    stop_seconds: float = Field(default=3, ge=.5, le=60)
    hard_braking_acceleration: float = Field(default=-4, ge=-20, le=-.5)
    wrong_way_seconds: float = Field(default=1, ge=.5, le=30)
    legal_direction: Point = (0, 1)

    @model_validator(mode='after')
    def valid_direction(self):
        if not all(math.isfinite(x) for x in self.legal_direction) or math.hypot(*self.legal_direction) < .001:
            raise ValueError('道路正常行驶方向不能为零')
        return self


class TemplateTarget(BaseModel):
    video_token: str
    scene_revision: int = Field(ge=0)


class TemplateCreate(TemplateTarget):
    name: str = Field(min_length=1, max_length=60)
    note: str = Field(default='', max_length=1000)


class TemplateRevision(BaseModel):
    revision: int = Field(ge=1)


class TemplateRename(TemplateRevision):
    name: str = Field(min_length=1, max_length=60)
    note: str = Field(default='', max_length=1000)


class TemplatePreview(TemplateTarget):
    template_revision: int = Field(ge=1)


class TemplateApply(TemplatePreview):
    geometry_confirmed: bool = False
    copy_scale: bool = False
    scale_confirmed: bool = False
