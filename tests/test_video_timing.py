import shutil
import subprocess
import cv2
import numpy as np
import pytest
from backend.vision.video_reader import VideoReader
import backend.vision.video_reader as module


def test_seek_uses_decoded_pts_even_when_millisecond_seek_would_be_wrong(monkeypatch):
    class Capture:
        times = [0, .12, .4, .84]
        def __init__(self, *args): self.index = 0; self.timestamp = 0
        def isOpened(self): return True
        def get(self, key):
            return {cv2.CAP_PROP_FRAME_WIDTH:160, cv2.CAP_PROP_FRAME_HEIGHT:96, cv2.CAP_PROP_FPS:7.142857,
                    cv2.CAP_PROP_FRAME_COUNT:4, cv2.CAP_PROP_POS_FRAMES:self.index, cv2.CAP_PROP_POS_MSEC:self.timestamp*1000}.get(key, 0)
        def set(self, key, value):
            if key != cv2.CAP_PROP_POS_FRAMES: raise AssertionError('must not seek using average FPS milliseconds')
            self.index = int(value); return True
        def read(self):
            if self.index >= 4: return False, None
            self.timestamp = self.times[self.index]; self.index += 1
            return True, np.zeros((96,160,3),np.uint8)
        def release(self): pass
    monkeypatch.setattr(module.cv2, 'VideoCapture', Capture)
    reader = VideoReader('test.mp4')
    reader.seek(.4)
    assert reader.read()[:2] == (2, .4)
    assert reader.read()[:2] == (3, .84)
    reader.seek(.2)
    assert reader.read()[:2] == (2, .4)
    reader.seek(0)
    assert reader.read()[:2] == (0, 0)


class FlexibleCapture:
    times = [0, .1, .2, .3]

    def __init__(self, *args, frames=4):
        self.index = 0
        self.timestamp = 0
        self.advertised_frames = frames

    def isOpened(self):
        return True

    def get(self, key):
        return {cv2.CAP_PROP_FRAME_WIDTH: 160, cv2.CAP_PROP_FRAME_HEIGHT: 96, cv2.CAP_PROP_FPS: 10,
                cv2.CAP_PROP_FRAME_COUNT: self.advertised_frames, cv2.CAP_PROP_POS_FRAMES: self.index,
                cv2.CAP_PROP_POS_MSEC: self.timestamp * 1000}.get(key, 0)

    def set(self, key, value):
        if key == cv2.CAP_PROP_POS_FRAMES:
            if not 0 <= value < len(self.times):
                return False
            self.index = int(value)
            return True
        if key == cv2.CAP_PROP_POS_MSEC:
            seconds = value / 1000
            matching = [i for i, timestamp in enumerate(self.times) if timestamp + 1e-9 >= seconds]
            if not matching:
                return False
            self.index = matching[0]
            return True
        return False

    def read(self):
        if self.index >= len(self.times):
            return False, None
        self.timestamp = self.times[self.index]
        self.index += 1
        return True, np.zeros((96, 160, 3), np.uint8)

    def release(self):
        pass


def test_seek_clamps_to_last_decodable_frame_when_count_is_overreported(monkeypatch):
    monkeypatch.setattr(module.cv2, 'VideoCapture', lambda *args: FlexibleCapture(frames=50))
    reader = VideoReader('test.mp4')
    reader.seek(.35)
    assert reader.read()[:2] == (3, .3)


def test_seek_falls_back_to_msec_when_frame_count_is_zero(monkeypatch):
    monkeypatch.setattr(module.cv2, 'VideoCapture', lambda *args: FlexibleCapture(frames=0))
    reader = VideoReader('test.mp4')
    reader.seek(.2)
    assert reader.read()[:2] == (2, .2)
    assert reader.read()[:2] == (3, .3)


def test_actual_vfr_mp4_read_and_seek(tmp_path):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg: pytest.skip('optional codec integration check requires ffmpeg')
    for i in range(4): cv2.imwrite(str(tmp_path / f'{i}.png'), np.full((96,160,3), i*50, np.uint8))
    listing = tmp_path / 'frames.txt'
    listing.write_text("file '0.png'\nduration 0.12\nfile '1.png'\nduration 0.28\nfile '2.png'\nduration 0.44\nfile '3.png'\n")
    path = tmp_path / 'vfr.mp4'
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing), '-fps_mode', 'vfr', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True, timeout=15)
    reader = VideoReader(path)
    try:
        assert [reader.read()[1] for _ in range(4)] == pytest.approx([0, .12, .4, .84])
        reader.seek(.4)
        assert reader.read()[:2] == (2, .4)
        assert reader.read()[:2] == (3, .84)
    finally:
        reader.close()


def test_video_reader_opens_unicode_file_path(tmp_path):
    source = tmp_path / 'ascii.mp4'
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'mp4v'), 10, (160, 96))
    if not writer.isOpened():
        pytest.skip('optional codec unavailable')
    for i in range(3):
        writer.write(np.full((96, 160, 3), i * 40, np.uint8))
    writer.release()
    folder = tmp_path / '中文目录'
    folder.mkdir()
    target = folder / '演示视频.mp4'
    shutil.copy2(source, target)
    reader = VideoReader(target)
    try:
        assert reader.read() is not None
    finally:
        reader.close()
