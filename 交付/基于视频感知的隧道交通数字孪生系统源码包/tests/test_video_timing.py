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
