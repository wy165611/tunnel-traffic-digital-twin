from collections import deque
from dataclasses import dataclass, field
from backend.traffic.speed_estimator import SpeedEstimator


@dataclass
class VehicleState:
    estimator: SpeedEstimator
    trajectory: deque = field(default_factory=lambda: deque(maxlen=100))
    world_trajectory: deque = field(default_factory=lambda: deque(maxlen=100))
    warning: str | None = None
    warning_until: float = 0.
    speed: float | None = None
    acceleration: float | None = None
