import hashlib
import math
import os
import time
from pathlib import Path
import cv2
from backend.traffic.counting_line import video_orientation


def _capture_source(path):
    """Use a Windows 8.3 short path because OpenCV may reject Unicode paths."""
    if os.name != 'nt':
        return path
    try:
        import ctypes
        from ctypes import wintypes
        get_short = ctypes.windll.kernel32.GetShortPathNameW
        get_short.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        get_short.restype = wintypes.DWORD
        buffer = ctypes.create_unicode_buffer(32768)
        length = get_short(str(path), buffer, len(buffer))
        return buffer.value if 0 < length < len(buffer) else path
    except (AttributeError, OSError, ValueError):
        return path


def video_identity(path):
    """Content based identity preserves calibration across reimports/renames."""
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()[:24]


class VideoReader:
    """Same reader interface for recordings and live RTSP/HTTP ingestion."""
    CAPTURE_OPTIONS = 'OPENCV_FFMPEG_CAPTURE_OPTIONS'

    def __init__(self, source, max_side=960, open_timeout=None, read_timeout=None):
        source = str(source)
        self.source = source
        self.live = source.lower().startswith(('rtsp://', 'rtsps://', 'http://', 'https://'))
        self.open_timeout = self._timeout(open_timeout, 8.)
        self.read_timeout = self._timeout(read_timeout, 10.)
        self.cap = self._open_capture()
        if not self.cap.isOpened():
            self.close()
            raise ValueError('视频无法打开，请检查文件或流地址')
        self.last_timestamp = None
        self.index = 0
        self.pending = None
        self._last_raw = None
        self._time_offset = 0.
        self._resume_on_next = False
        self.stream_state = 'connected' if self.live else None
        self.reconnect_attempt = 0
        self.stream_error = None
        self._retry_delay = 1.
        self._next_retry = 0.
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

    @staticmethod
    def _timeout(value, default):
        try:
            return min(120., max(1., float(value)))
        except (TypeError, ValueError):
            return default

    def _open_capture(self):
        """Prefer RTSP over TCP and bound both open and read blocking."""
        if not self.live:
            return cv2.VideoCapture(_capture_source(self.source))
        options = os.environ.get(self.CAPTURE_OPTIONS, '').strip()
        if 'rtsp_transport' not in options:
            options = (options+';' if options else '')+'rtsp_transport;tcp'
        os.environ[self.CAPTURE_OPTIONS] = options
        params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(self.open_timeout*1000),
                  cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(self.read_timeout*1000)]
        try:
            return cv2.VideoCapture(self.source, cv2.CAP_FFMPEG, params)
        except (TypeError, cv2.error):
            # Older OpenCV builds lack the params overload; keep the stream usable.
            return cv2.VideoCapture(self.source)

    @property
    def metadata(self):
        return dict(width=self.width, height=self.height, fps=self.fps,
                    orientation=video_orientation(self.width, self.height),
                    frames=self.frames, duration=self.duration, duration_estimated=self.duration_estimated, timing_source='decoder_pts',
                    display_width=self.display_width, display_height=self.display_height,
                    live=self.live, stream_state=self.stream_state,
                    reconnect_attempt=self.reconnect_attempt, stream_error=self.stream_error)

    def _schedule_retry(self, message):
        self.stream_state, self.stream_error = 'reconnecting', message
        self.reconnect_attempt += 1
        self._retry_delay = min(30., 2.**(self.reconnect_attempt-1))
        self._next_retry = time.monotonic()+self._retry_delay

    def _maybe_reconnect(self):
        if time.monotonic() < self._next_retry:
            return False
        cap = self._open_capture()
        if cap.isOpened():
            previous = self.cap
            self.cap = cap
            previous.release()
            self.stream_state, self.stream_error = 'connected', None
            self.reconnect_attempt, self._retry_delay, self._next_retry = 0, 1., 0.
            self._last_raw = None
            self._resume_on_next = self.last_timestamp is not None
            return True
        cap.release()
        self._schedule_retry('视频流重连失败')
        return False

    def _live_timestamp(self, raw):
        if not math.isfinite(raw) or raw < 0:
            raw = None
        if raw is None or (self._last_raw is not None and raw <= self._last_raw):
            raw = (self._last_raw if self._last_raw is not None else 0.)+1/self.fps
        self._last_raw = raw
        if self._resume_on_next:
            base = self.last_timestamp if self.last_timestamp is not None else 0.
            self._time_offset = base+1/self.fps-raw
            self._resume_on_next = False
        return raw+self._time_offset

    def read(self):
        if self.pending is not None:
            index, timestamp, frame = self.pending
            self.pending = None
        else:
            if self.live and self.stream_state == 'reconnecting' and not self._maybe_reconnect():
                return None
            ok, frame = self.cap.read()
            if not ok:
                if not self.live:
                    return None
                self._schedule_retry('视频流连接已断开')
                return None
            index = self.index
            raw = self.cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            if self.live:
                timestamp = self._live_timestamp(raw)
            else:
                timestamp = raw
        self.index = index + 1
        if self.live:
            self.last_timestamp = timestamp
        else:
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
        if self.frames > 0:
            seconds = min(seconds, max(0, self.duration-1/self.fps))
        self.pending = None
        self.last_timestamp = None
        if seconds == 0:
            if not self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0):
                self._seek_by_msec(0)
                return
            self.index = 0
            return
        # CAP_PROP_POS_MSEC can silently use average FPS on VFR MP4. Locate the
        # first actual decoded PTS >= the requested time by frame-index probes.
        index_error = None
        if self.frames > 0:
            try:
                self._seek_by_frame_index(seconds)
                return
            except ValueError as exc:
                index_error = exc
        try:
            self._seek_by_msec(seconds)
        except ValueError as exc:
            if index_error is not None:
                raise index_error from exc
            raise

    def _seek_by_frame_index(self, seconds):
        low, high, selected, last_decodable = 0, self.frames - 1, None, None
        while low <= high:
            middle = (low + high) // 2
            try:
                _, timestamp, _ = self._probe(middle)
            except ValueError:
                # CAP_PROP_FRAME_COUNT can exceed the decodable range.
                high = middle - 1
                continue
            last_decodable = middle
            if timestamp + 1e-7 < seconds:
                low = middle + 1
            else:
                selected = middle
                high = middle - 1
        if selected is None:
            selected = last_decodable
        if selected is None:
            raise ValueError('视频解码器不支持准确定位，请转换为恒定帧率 MP4')
        self.pending = self._probe(selected)
        self.index = selected

    def _seek_by_msec(self, seconds):
        if not self.cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000):
            raise ValueError('视频解码器不支持准确定位，请转换为恒定帧率 MP4')
        ok, frame = self.cap.read()
        timestamp = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        if not ok or not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError('视频解码器无法定位目标帧，请转换为恒定帧率 MP4')
        index = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
        if index < 0:
            index = int(round(timestamp * self.fps))
        self.pending = (index, timestamp, frame)
        self.index = index

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
