import hashlib
import math
from pathlib import Path
import cv2
from backend.traffic.counting_line import video_orientation


def video_identity(path):
    """Content based identity preserves calibration across reimports/renames."""
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()[:24]


class VideoReader:
    """Same reader interface for recordings and future RTSP ingestion."""
    def __init__(self, source, max_side=960):
        self.live = str(source).startswith(('rtsp://', 'rtsps://'))
        self.cap = cv2.VideoCapture(str(source))
        if not self.cap.isOpened():
            raise ValueError('视频无法打开，请检查文件或流地址')
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        if not math.isfinite(self.fps) or self.fps <= 0:
            self.close()
            raise ValueError('视频帧率无效')
        self.frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) if not self.live else 0
        if not self.width or not self.height:
            self.close()
            raise ValueError('无效视频尺寸')
        scale = min(1., max_side / max(self.width, self.height))
        self.display_width = round(self.width * scale)
        self.display_height = round(self.height * scale)
        self.index = 0
        self.pending = None
        self.last_timestamp = None
        self.duration = self.frames / self.fps
        self.duration_estimated = True
        # The last decoded PTS avoids an average-FPS duration cutting off VFR input.
        if not self.live and self.frames > 1:
            if self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.frames - 1):
                ok, _ = self.cap.read()
                last_pts = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                if ok and math.isfinite(last_pts) and last_pts > 0:
                    self.duration = last_pts + 1 / self.fps
                    self.duration_estimated = False
            if not self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0):
                self.close()
                raise ValueError('视频解码器无法回到起点')

    @property
    def metadata(self):
        return dict(width=self.width, height=self.height, fps=self.fps,
                    orientation=video_orientation(self.width, self.height),
                    frames=self.frames, duration=self.duration, duration_estimated=self.duration_estimated, timing_source='decoder_pts',
                    display_width=self.display_width, display_height=self.display_height,
                    live=self.live)

    def read(self):
        if self.pending is not None:
            index, timestamp, frame = self.pending
            self.pending = None
        else:
            ok, frame = self.cap.read()
            if not ok:
                return None
            index = self.index
            timestamp = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        self.index = index + 1
        if not math.isfinite(timestamp) or timestamp < 0 or (self.last_timestamp is not None and timestamp <= self.last_timestamp):
            raise ValueError('视频解码器未提供单调时间戳，请将视频转换为恒定帧率 MP4 后重试')
        self.last_timestamp = timestamp
        self.duration = max(self.duration, timestamp + 1 / self.fps)
        frame = cv2.resize(frame, (self.display_width, self.display_height))
        return index, timestamp, frame

    def seek(self, seconds):
        if self.live:
            raise ValueError('实时流不支持拖动')
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError('拖动时间必须为有限的非负值')
        seconds = min(seconds, max(0, self.duration-1/self.fps))
        self.pending = None
        self.last_timestamp = None
        if seconds == 0:
            if not self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0):
                raise ValueError('视频解码器不支持定位')
            self.index = 0
            return
        # CAP_PROP_POS_MSEC can silently use average FPS on VFR MP4. Locate the
        # first actual decoded PTS >= the requested time by frame-index probes.
        low, high, selected = 0, self.frames - 1, None
        while low <= high:
            middle = (low + high) // 2
            _, timestamp, _ = self._probe(middle)
            if timestamp + 1e-7 < seconds:
                low = middle + 1
            else:
                selected = middle
                high = middle - 1
        if selected is None:
            selected = self.frames - 1
        self.pending = self._probe(selected)
        self.index = selected

    def _probe(self, index):
        if index < 0 or not self.cap.set(cv2.CAP_PROP_POS_FRAMES, index):
            raise ValueError('视频解码器不支持准确定位，请转换为恒定帧率 MP4')
        ok, frame = self.cap.read()
        timestamp = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        actual_index = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
        if not ok or actual_index != index or not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError('视频解码器无法定位目标帧，请转换为恒定帧率 MP4')
        return index, timestamp, frame

    def close(self):
        self.cap.release()
