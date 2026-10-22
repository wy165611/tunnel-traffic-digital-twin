import asyncio
import copy
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
from backend.settings import DATA, ROOT, load_config
from backend.calibration.homography import RoadCalibration, normalised_direction
from backend.exporter import atomic_json
from backend.processor import TrafficProcessor, encode_frame
from backend.vision.detector import VehicleDetector, model_supports_intrusion
from backend.vision.video_reader import VideoReader, video_identity
from backend.traffic.counting_line import automatic_counting_line, resolve_counting_line
from backend.traffic.service_level import scene_loops


class StaleVideoError(ValueError):
    pass


class AnalysisService:
    def __init__(self):
        self.config = load_config()
        self.detector = self.reader = self.processor = None
        self.status, self.error, self.rate = 'idle', None, 1.
        self.video_id = self.identity = self.video_token = None
        self.session_id = uuid4().hex
        self.scene_revision = 0
        self.scene = dict(counting_line=None, lanes=[], speed_limit_kmh=None)
        self.calibration = None
        self.template_provenance = None
        self.snapshot = {}
        self.revision = 0
        self.lock = asyncio.Lock()
        self._publish()

    def _publish(self):
        # Publish complete immutable snapshots once; worker threads never expose a half-swapped video.
        scene = copy.deepcopy(self.scene)
        scene['virtual_loops'] = scene_loops(scene.get('lanes') or [])
        calibration = self.effective_calibration
        self._state = dict(**self.snapshot, status=self.status, error=self.error, rate=self.rate,
            session_id=self.session_id, revision=self.revision, video_id=self.video_id,
            video_token=self.video_token, scene_revision=self.scene_revision,
            video=self.reader.metadata if self.reader else None, template_provenance=copy.deepcopy(self.template_provenance), scene=scene,
            calibration=copy.deepcopy(self.calibration.payload) if self.calibration else None,
            calibration_notice=self.calibration_notice,
            counting_line_suggestion=automatic_counting_line(self.reader.width, self.reader.height, self.scene.get('lanes')) if self.reader else None,
            settings=dict(model=self.config['detector']['model'], confidence=self.config['detector']['confidence'],
                detection_interval=self.config['video']['detection_interval'], smoothing_frames=self.config['speed']['smoothing_frames'],
                intrusion_supported=model_supports_intrusion(self.config['detector']['model']),
                calibration_available=calibration is not None,
                calibration_required_metrics=['speed', 'tailgating', 'queue_length_m', 'density', 'service_level'],
                alert_cooldown_seconds=float(self.config.get('alerts', {}).get('cooldown_seconds', 10)),
                occupancy_enabled=bool(self.config['traffic'].get('time_occupancy_enabled', True)),
                low_light_enabled=bool(self.config.get('preprocessing', {}).get('low_light_enabled', False)),
                low_light_clahe_clip=float(self.config.get('preprocessing', {}).get('clahe_clip_limit', 2.)),
                low_light_gamma=float(self.config.get('preprocessing', {}).get('gamma', 1.5)),
                **self.config['events'], legal_direction=list(self.config['traffic']['legal_direction'])))

    def state(self):
        return dict(self._state)

    @property
    def calibration_notice(self):
        """A live resolution switch makes the saved metric scale untrustworthy."""
        change = getattr(self.reader, 'resolution_change', None) if self.reader else None
        if not change or not getattr(self.reader, 'resolution_changed', False):
            return None
        previous, current = change['previous'], change['current']
        return dict(reason='resolution_changed',
                    message=f"实时流分辨率已从 {previous[0]}×{previous[1]} 变为 {current[0]}×{current[1]}，原标定已失效，请重新标定后再启用测速、跟车时距、排队米数与服务水平。",
                    previous=list(previous), current=list(current))

    @property
    def effective_calibration(self):
        return None if self.calibration_notice else self.calibration

    def changed(self):
        self.revision += 1
        self._publish()

    def _sync_legal_direction(self):
        """Keep the default legal direction on the detected travel axis.

        A user-selected forward/reverse sign is preserved; a perpendicular
        direction (the legacy default on landscape roads) is reset to +Y,
        which always follows the auto-detected road-length edge.
        """
        if not self.effective_calibration:
            return
        current = normalised_direction(self.config['traffic']['legal_direction'])
        travel = self.effective_calibration.travel_direction.tolist()
        if abs(current[0]*travel[0]+current[1]*travel[1]) < .5:
            current = travel
        self.config['traffic']['legal_direction'] = current

    @staticmethod
    def read_preview(reader, seconds):
        if not reader.live:
            reader.seek(seconds)
        item = reader.read()
        if item is None:
            raise ValueError('视频没有可读取的帧')
        index, timestamp, frame = item
        image = encode_frame(frame)
        if not reader.live:
            reader.seek(timestamp)
        return dict(image=image, frame=index, timestamp=timestamp, vehicles=[], events=[], history=[], metrics=None)

    def select_sync(self, video_id):
        path = DATA / 'videos' / video_id
        if Path(video_id).name != video_id or not path.is_file():
            raise ValueError('视频不存在')
        reader = VideoReader(path, self.config['video']['display_max_side'])
        try:
            identity = video_identity(path)
            scene_file = DATA / 'calibrations' / f'{identity}-scene.json'
            scene = json.loads(scene_file.read_text(encoding='utf-8')) if scene_file.exists() else dict(counting_line=None, lanes=[], speed_limit_kmh=None)
            calibration = RoadCalibration.load(DATA / 'calibrations' / f'{identity}-calibration.json', scene=scene)
            resolved = resolve_counting_line(scene, reader.width, reader.height)
            preview = self.read_preview(reader, 0)
            if resolved != scene:
                atomic_json(scene_file, resolved)
        except Exception:
            reader.close()
            raise
        # Nothing above changes the current session. An invalid new video preserves the old one.
        if self.processor:
            self.processor.close()
        if self.reader:
            self.reader.close()
        self.processor = None
        self.reader, self.identity, self.video_id = reader, identity, video_id
        self.video_token, self.scene_revision = uuid4().hex, 0
        self.scene, self.calibration, self.snapshot = resolved, calibration, preview
        self._sync_legal_direction()
        self.template_provenance = copy.deepcopy(resolved.get('template_provenance'))
        self.status, self.error = 'ready', None
        self.changed()

    def preview_sync(self, seconds):
        try:
            preview = self.read_preview(self.reader, seconds)
        except Exception as exc:
            self.status, self.error = 'error', str(exc)
            self.changed()
            raise
        self.snapshot, self.status, self.error = preview, 'ready', None
        self.changed()

    def reset_processor_sync(self, seconds=0):
        if self.processor:
            self.processor.close()
            self.processor = None
        preview = self.read_preview(self.reader, seconds)
        calibration = self.effective_calibration
        self.processor = TrafficProcessor(self.reader, self.detector, copy.deepcopy(self.config), self.scene, calibration, preview['timestamp'])
        self.processor.exporter.update_metadata(video_id=self.video_id, video_identity=self.identity,
            segment_start=preview['timestamp'], calibrated=calibration is not None,
            config=copy.deepcopy(self.config), scene=copy.deepcopy(self.scene),
            calibration=calibration.payload if calibration else None,
            video=self.reader.metadata, template_provenance=copy.deepcopy(self.template_provenance))
        self.snapshot = dict(**preview, run_id=self.processor.exporter.run_id, segment_start=preview['timestamp'])

    async def select(self, video_id):
        async with self.lock:
            await asyncio.to_thread(self.select_sync, video_id)

    def select_stream_sync(self, url):
        url = url.strip()
        if not url.lower().startswith(('rtsp://', 'rtsps://', 'http://', 'https://')):
            raise ValueError('流地址必须以 rtsp://、rtsps://、http:// 或 https:// 开头')
        reader = VideoReader(url, open_timeout=self.config['video'].get('stream_open_timeout_seconds'),
                             read_timeout=self.config['video'].get('stream_read_timeout_seconds'))
        try:
            identity = 'stream-'+hashlib.sha256(url.encode('utf-8')).hexdigest()[:24]
            scene_file = DATA / 'calibrations' / f'{identity}-scene.json'
            scene = json.loads(scene_file.read_text(encoding='utf-8')) if scene_file.exists() else dict(
                counting_line=None, lanes=[], speed_limit_kmh=None)
            calibration = RoadCalibration.load(DATA / 'calibrations' / f'{identity}-calibration.json', scene=scene)
            resolved = resolve_counting_line(scene, reader.width, reader.height)
            preview = self.read_preview(reader, 0)
            if resolved != scene:
                atomic_json(scene_file, resolved)
        except Exception:
            reader.close()
            raise
        if self.processor:
            self.processor.close()
        if self.reader:
            self.reader.close()
        self.processor = None
        self.reader, self.identity = reader, identity
        self.video_id = '实时流 · '+(urlsplit(url).hostname or 'stream')
        self.video_token, self.scene_revision = uuid4().hex, 0
        self.scene, self.calibration, self.snapshot = resolved, calibration, preview
        self._sync_legal_direction()
        self.template_provenance = copy.deepcopy(resolved.get('template_provenance'))
        self.status, self.error = 'ready', None
        self.changed()

    async def select_stream(self, url):
        async with self.lock:
            await asyncio.to_thread(self.select_stream_sync, url)

    def check_target(self, payload):
        if self.reader and payload.video_token != self.video_token:
            raise StaleVideoError('视频已切换，请重新打开当前视频的设置')
        expected = getattr(payload, 'scene_revision', None)
        if expected is not None and expected != self.scene_revision:
            raise StaleVideoError('道路配置已被另一个窗口更新，请关闭面板并重新打开')

    async def control(self, control):
        async with self.lock:
            if not self.reader:
                raise ValueError('请先选择视频')
            action = control.action
            if action == 'pause':
                self.status = 'paused'
            elif action == 'rate':
                self.rate = control.rate
            elif action == 'seek':
                if self.reader.live:
                    raise ValueError('实时流不支持拖动')
                self.status = 'paused'
                if self.processor:
                    self.processor.close()
                    self.processor = None
                await asyncio.to_thread(self.preview_sync, control.seconds)
            elif action in ('play', 'restart'):
                resume_from_ended = self.status == 'ended'
                self.status, self.error = 'loading', None
                self.changed()
                try:
                    if self.detector is None:
                        self.detector = await asyncio.to_thread(VehicleDetector, self.config['detector'])
                    at_end = self.reader.frames > 0 and self.reader.index >= self.reader.frames
                    if action == 'restart' or self.processor is None or resume_from_ended or at_end:
                        seconds = 0 if action == 'restart' or resume_from_ended or at_end else self.snapshot.get('timestamp', 0)
                        await asyncio.to_thread(self.reset_processor_sync, seconds)
                    self.status = 'playing'
                except Exception as exc:
                    self.status, self.error = 'error', str(exc)
                    self.changed()
                    raise
            self.changed()

    async def save_scene(self, payload):
        async with self.lock:
            await self.save_scene_locked(payload)

    async def save_scene_locked(self, payload, provenance=None):
        if self.reader is None:
            raise ValueError('请先导入视频')
        self.check_target(payload)
        data = payload.model_dump(mode='json', exclude={'video_token', 'scene_revision'})
        all_points = list(data.get('points') or []) + list(data.get('counting_line') or [])
        for lane in data['lanes']:
            all_points.extend(lane['points'])
            all_points.extend(lane.get('loop') or [])
        if any(not (0 <= p[0] <= self.reader.width and 0 <= p[1] <= self.reader.height) for p in all_points):
            raise ValueError('绘制坐标必须位于视频画面内')
        calibration = RoadCalibration(data) if data['points'] else None
        mode = data['counting_line_mode'] or ('manual' if data['counting_line'] else 'disabled')
        scene = resolve_counting_line(dict(counting_line=data['counting_line'], lanes=data['lanes'],
                                           speed_limit_kmh=data.get('speed_limit_kmh'), counting_line_mode=mode),
                                      self.reader.width, self.reader.height)
        try:
            preview = await asyncio.to_thread(self.read_preview, self.reader, self.snapshot.get('timestamp', 0))
        except Exception as exc:
            self.status, self.error = 'error', str(exc)
            self.changed()
            raise
        path = DATA / 'calibrations' / f'{self.identity}-calibration.json'
        if calibration:
            atomic_json(path, calibration.payload)
            atomic_json(DATA / 'calibration.json', calibration.payload)
        else:
            path.unlink(missing_ok=True)
        if provenance:
            scene['template_provenance'] = copy.deepcopy(provenance)
        atomic_json(DATA / 'calibrations' / f'{self.identity}-scene.json', scene)
        if self.processor:
            self.processor.close()
            self.processor = None
        self.scene, self.calibration, self.snapshot = scene, calibration, preview
        if self.reader:
            # Re-drawn corners on the current stream restore the metric gate.
            self.reader.clear_resolution_change()
        self._sync_legal_direction()
        self.template_provenance = copy.deepcopy(provenance)
        self.scene_revision += 1
        self.status, self.error = 'ready', None
        self.changed()

    async def configure(self, settings):
        async with self.lock:
            self.check_target(settings)
            # Stop first so a failed preview can never leave playing + no processor.
            self.status = 'paused' if self.reader else 'idle'
            if self.reader:
                await asyncio.to_thread(self.preview_sync, self.snapshot.get('timestamp', 0))
            if self.config['detector']['model'] != settings.model:
                self.detector = None
            self.config['detector'].update(model=settings.model, confidence=settings.confidence)
            self.config['video']['detection_interval'] = settings.detection_interval
            self.config['speed']['smoothing_frames'] = settings.smoothing_frames
            for name in ('stop_speed', 'stop_seconds', 'hard_braking_acceleration', 'wrong_way_seconds',
                         'speeding_enabled', 'speeding_kmh', 'slow_speed_enabled', 'slow_speed_kmh',
                         'lane_change_enabled', 'lane_change_seconds', 'tailgating_enabled',
                         'tailgating_headway_seconds', 'intrusion_enabled', 'queue_speed_kmh'):
                self.config['events'][name] = getattr(settings, name)
            self.config['traffic']['legal_direction'] = normalised_direction(settings.legal_direction)
            self.config['traffic']['time_occupancy_enabled'] = settings.occupancy_enabled
            self.config.setdefault('preprocessing', {}).update(low_light_enabled=settings.low_light_enabled,
                clahe_clip_limit=settings.low_light_clahe_clip, gamma=settings.low_light_gamma)
            if self.detector:
                self.detector.config = self.config['detector']
            if self.processor:
                self.processor.close()
                self.processor = None
            self.changed()

    async def run(self):
        while True:
            if self.status not in ('playing', 'reconnecting'):
                await asyncio.sleep(.05)
                continue
            started = asyncio.get_running_loop().time()
            frame_interval = 1 / self.reader.fps if self.reader else .05
            async with self.lock:
                if self.status in ('playing', 'reconnecting') and self.processor is None:
                    self.status, self.error = 'error', '分析状态已失效，请重新开始分析'
                    self.changed()
                elif self.status in ('playing', 'reconnecting'):
                    try:
                        previous = self.snapshot.get('timestamp')
                        step_task = asyncio.create_task(asyncio.to_thread(self.processor.step))
                        try:
                            frame = await asyncio.shield(step_task)
                        except asyncio.CancelledError:
                            await step_task
                            raise
                        if frame is None:
                            if self.reader and self.reader.live:
                                self.status = 'reconnecting'
                                self.error = self.reader.metadata.get('stream_error') or '实时流已断开，正在重连'
                            else:
                                self.status = 'ended'
                        else:
                            if self.reader and self.reader.live and self.status == 'reconnecting':
                                self.status, self.error = 'playing', None
                            if previous is not None and frame['timestamp'] > previous:
                                frame_interval = frame['timestamp'] - previous
                            if self.reader and self.reader.metadata.get('resolution_changed') and self.processor:
                                self.processor.invalidate_calibration()
                            self.snapshot = frame
                        self.changed()
                    except Exception as exc:
                        self.status, self.error = 'error', str(exc)
                        self.changed()
            elapsed = asyncio.get_running_loop().time() - started
            await asyncio.sleep(max(.001, frame_interval / self.rate - elapsed))

    def close(self):
        if self.processor:
            self.processor.close()
        if self.reader:
            self.reader.close()
