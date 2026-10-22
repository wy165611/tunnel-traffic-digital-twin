import numpy as np
import pytest
from backend.events import debris
from backend.events.rules import EVENT_NAMES

LANE = dict(name='Lane 1', points=[[10, 10], [90, 10], [90, 90], [10, 90]], direction=[0, 1])


def detector(scene=None, **overrides):
    config = dict(debris_enabled=True, debris_seconds=2., debris_area_ratio=.18,
                  debris_difference_threshold=25, debris_cooldown_seconds=30.)
    config.update(overrides)
    return debris.DebrisDetector(scene or dict(lanes=[LANE]), config, 100, 100, 1.)


def frame(block=None):
    image = np.zeros((100, 100, 3), np.uint8)
    if block:
        y1, y2, x1, x2 = block
        image[y1:y2, x1:x2] = 255
    return image


def vehicle(pixel=(50, 50), box=(40, 40, 60, 60)):
    return dict(observed=True, pixel=list(pixel), box=list(box))


def test_static_foreground_on_loop_raises_road_debris_after_duration():
    detector_ = detector()
    assert detector_.enabled is True
    assert detector_.update(0., frame()) == []
    block = (30, 70, 30, 70)
    assert detector_.update(1., frame(block)) == []
    assert detector_.update(2., frame(block)) == []
    results = detector_.update(3., frame(block))
    assert len(results) == 1
    event, target = results[0]
    assert event['event'] == 'ROAD DEBRIS' and event['label'] == EVENT_NAMES['ROAD DEBRIS'] == '路面异物'
    assert event['vehicle_id'] == -1 and event['lane'] == 'Lane 1'
    assert target['type'] == 'debris' and target['lane'] == 'Lane 1'
    assert target['box'][0] < target['box'][2] and target['box'][1] < target['box'][3]


def test_observed_vehicle_inside_loop_suppresses_debris():
    detector_ = detector()
    block = (30, 70, 30, 70)
    detector_.update(0., frame())
    for timestamp in (1., 2., 3., 4.):
        assert detector_.update(timestamp, frame(block), [vehicle()]) == []
    assert detector_.update(5., frame(block)) == []  # clock restarts after the vehicle leaves
    assert len(detector_.update(7., frame(block))) == 1


def test_cooldown_limits_repeated_debris_events():
    detector_ = detector(debris_cooldown_seconds=5.)
    block = (30, 70, 30, 70)
    detector_.update(0., frame())
    detector_.update(1., frame(block))
    assert len(detector_.update(3., frame(block))) == 1
    assert detector_.update(7., frame(block)) == []
    assert len(detector_.update(8., frame(block))) == 1


def test_area_ratio_threshold_ignores_small_foreground_patches():
    detector_ = detector()
    detector_.update(0., frame())
    small = (40, 50, 40, 50)
    assert detector_.update(1., frame(small)) == []
    assert detector_.update(4., frame(small)) == []
    assert detector_.loops['Lane 1']['area'] > 100


def test_without_lanes_or_switch_debris_stays_disabled():
    assert detector(scene=dict(lanes=[])).enabled is False
    assert detector(scene=dict(lanes=[])).update(1., frame((30, 70, 30, 70))) == []
    off = detector(debris_enabled=False)
    assert off.enabled is False and off.update(1., frame((30, 70, 30, 70))) == []


def test_debris_thresholds_are_sanitized_and_scaled():
    detector_ = detector(debris_seconds=.1, debris_area_ratio=5, debris_difference_threshold=999)
    assert detector_.seconds == pytest.approx(.5)
    assert detector_.area_ratio == 1 and detector_.threshold == 255
    scaled = debris.DebrisDetector(dict(lanes=[LANE]), detector_.config, 50, 50, .5)
    assert scaled.enabled is True and scaled.loops['Lane 1']['points'].max() <= 49
