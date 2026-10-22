import numpy as np
import pytest
from backend.processor import TrafficProcessor
from backend.settings import load_config
from backend.vision.enhance import LowLightEnhancer
from test_api import client


def dark_frame():
    frame = np.zeros((120, 160, 3), np.uint8)
    frame[:, :, 2] = np.linspace(5, 35, 160, dtype=np.uint8)[None, :]
    frame[:, :, 1] = 18
    frame[:, :, 0] = 10
    return frame


def test_enhancement_is_off_by_default_and_returns_the_same_frame():
    assert load_config()['preprocessing']['low_light_enabled'] is False
    frame = dark_frame()
    assert LowLightEnhancer({}).apply(frame) is frame
    assert LowLightEnhancer({'low_light_enabled': False, 'gamma': 2.}).apply(frame) is frame


def test_clahe_and_gamma_brighten_without_changing_shape():
    frame = dark_frame()
    enhanced = LowLightEnhancer({'low_light_enabled': True, 'clahe_clip_limit': 2., 'gamma': 1.8}).apply(frame)
    assert enhanced.shape == frame.shape and enhanced.dtype == np.uint8
    assert enhanced.mean() > frame.mean()*1.3
    assert enhanced[:, :, 2].mean() > frame[:, :, 2].mean()
    only_clahe = LowLightEnhancer({'low_light_enabled': True, 'gamma': 1.}).apply(frame)
    assert only_clahe.mean() > frame.mean()
    clamped = LowLightEnhancer({'low_light_enabled': True, 'clahe_clip_limit': 99, 'gamma': 99})
    assert clamped.clip_limit == 10 and clamped.gamma == 3


def test_processor_detects_brightened_frames_when_enabled():
    class Reader:
        width = height = 120
        display_width = display_height = 120
        fps = 10
        index = 0
        def read(self):
            i = self.index; self.index += 1
            return (i, i/10, dark_frame()) if i < 3 else None
    class Detector:
        device = 'cpu'; detect_ms = 1.
        def __init__(self): self.means = []
        def detect(self, frame): self.means.append(float(frame.mean())); return []
    config = load_config(); config['video']['detection_interval'] = 1
    config['preprocessing'].update(low_light_enabled=True, clahe_clip_limit=2., gamma=2.)
    detector = Detector()
    processor = TrafficProcessor(Reader(), detector, config, dict(lanes=[], counting_line=None))
    while processor.step() is not None:
        pass
    processor.close()
    assert detector.means and min(detector.means) > dark_frame().mean()*1.3


def test_settings_api_toggles_low_light_parameters(client):
    c, s = client
    assert c.get('/api/state').json()['settings']['low_light_enabled'] is False
    response = c.post('/api/settings', json={'low_light_enabled': True, 'low_light_clahe_clip': 3.5, 'low_light_gamma': 2.2})
    assert response.status_code == 200
    settings = response.json()['settings']
    assert settings['low_light_enabled'] is True
    assert settings['low_light_clahe_clip'] == 3.5 and settings['low_light_gamma'] == 2.2
    assert s.config['preprocessing']['clahe_clip_limit'] == 3.5
    assert c.post('/api/settings', json={'low_light_gamma': 0}).status_code == 422
    assert c.post('/api/settings', json={'low_light_clahe_clip': 11}).status_code == 422
