import asyncio
import json
import shutil
import re
import tempfile
from contextlib import suppress
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from backend.api.schemas import VideoSelection, PathImport, StreamInput, PlaybackControl, SceneInput, RuntimeSettings, TemplateCreate, TemplateRename, TemplateRevision, TemplatePreview, TemplateApply
from backend.alerts import DELIVERY_LOG
from backend.settings import DATA, ROOT
from backend.service import AnalysisService, StaleVideoError
from backend.security import UploadBodyLimit, MAX_VIDEO_BYTES, trusted_origin
from backend.vision.video_reader import VideoReader
from backend.reports import snapshot_run, build_report, compare_reports, report_html
from backend.evidence import event_detail, evidence_directory, source_path, list_events, save_review
from backend import camera_templates, annotations
from pydantic import BaseModel, Field
from typing import Literal

service = AnalysisService()


@asynccontextmanager
async def lifespan(app):
    default = DATA / 'videos' / Path(service.config['video']['default_video']).name
    if default.exists():
        try:
            await service.select(default.name)
        except (ValueError, OSError) as exc:
            service.status, service.error = 'error', str(exc)
            service.changed()
    task = asyncio.create_task(service.run())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    service.close()


app = FastAPI(title='隧道交通数字孪生监测系统', lifespan=lifespan)
app.add_middleware(UploadBodyLimit)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', '[::1]'])


@app.middleware('http')
async def browser_origin(request, call_next):
    from fastapi.responses import JSONResponse
    origin = request.headers.get('origin')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and not trusted_origin(origin, request.headers.get('host', '')):
        return JSONResponse({'detail': '不允许此页面来源修改本机分析状态'}, status_code=403)
    return await call_next(request)


@app.get('/api/health')
def health():
    return dict(ok=True, model=service.config['detector']['model'], model_loaded=service.detector is not None)


@app.get('/api/state')
def state():
    return service.state()


@app.get('/api/videos')
def videos():
    return [dict(id=p.name, name=p.name, bytes=p.stat().st_size) for p in sorted((DATA/'videos').iterdir()) if p.suffix.lower() in ('.mp4', '.mov', '.avi', '.mkv', '.webm')]


@app.post('/api/video/select')
async def select(payload: VideoSelection):
    try:
        await service.select(payload.video_id)
        return service.state()
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


def import_path(source):
    source = Path(source).expanduser()
    if not source.is_file() or source.suffix.lower() not in ('.mp4', '.mov', '.avi', '.mkv', '.webm'):
        raise ValueError('请选择可读取的 MP4/MOV/AVI/MKV/WebM 视频文件')
    if source.stat().st_size > MAX_VIDEO_BYTES:
        raise ValueError('视频文件不能超过 2 GB')
    reader = VideoReader(source)
    try:
        if reader.read() is None:
            raise ValueError('视频没有可读取的帧')
    finally:
        reader.close()
    target = DATA / 'videos' / (uuid4().hex[:8]+'-'+source.name)
    try:
        shutil.copy2(source, target)
    except OSError:
        target.unlink(missing_ok=True)
        raise
    return target.name


@app.post('/api/video/stream')
async def select_stream(payload: StreamInput):
    try:
        await service.select_stream(payload.url)
        return service.state()
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/video/import')
async def import_video(payload: PathImport):
    video_id = None
    imported = False
    try:
        video_id = await asyncio.to_thread(import_path, payload.path)
        await service.select(video_id)
        imported = True
        return service.state()
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        if not imported and video_id:
            (DATA / 'videos' / video_id).unlink(missing_ok=True)


@app.post('/api/video/upload')
async def upload(file: UploadFile):
    filename = Path(file.filename or 'video.mp4').name
    if Path(filename).suffix.lower() not in ('.mp4', '.mov', '.avi', '.mkv', '.webm'):
        raise HTTPException(400, '不支持的视频格式')
    target = DATA / 'videos' / (uuid4().hex[:8]+'-'+filename)
    size = 0
    imported = False
    try:
        with target.open('wb') as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_VIDEO_BYTES:
                    raise ValueError('视频文件不能超过 2 GB')
                f.write(chunk)
        await service.select(target.name)
        imported = True
        return service.state()
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        if not imported:
            target.unlink(missing_ok=True)
        await file.close()


@app.post('/api/control')
async def control(payload: PlaybackControl):
    try:
        await service.control(payload)
        return service.state()
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/calibration')
async def calibration(payload: SceneInput):
    try:
        await service.save_scene(payload)
        return service.state()
    except StaleVideoError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/settings')
async def settings(payload: RuntimeSettings):
    try:
        await service.configure(payload)
        return service.state()
    except StaleVideoError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/webhook-log')
def webhook_log(limit: int = 50, offset: int = 0, status: Literal['all', 'success', 'failed'] = 'all'):
    if not 1 <= limit <= 200 or offset < 0:
        raise HTTPException(400, '无效分页参数')
    alerts = service.config.get('alerts') or {}
    enabled = bool(alerts.get('webhook_enabled')) and bool(str(alerts.get('webhook_url') or '').strip())
    return dict(enabled=enabled, **DELIVERY_LOG.query(limit, offset, None if status == 'all' else status))


@app.get('/api/runs')
def runs():
    return [p.name for p in sorted((DATA/'runs').iterdir(), reverse=True) if p.is_dir()]


@app.get('/api/runs/details')
def run_details(limit: int = 30, offset: int = 0):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(400, '无效分页参数')
    folders = [p for p in sorted((DATA / 'runs').iterdir(), reverse=True) if p.is_dir() and re.fullmatch(r'\d{8}-\d{6}-[a-f0-9]{6}', p.name)]
    items = []
    for folder in folders[offset:offset + limit]:
        try:
            metadata = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            metadata = dict(run_id=folder.name, video_id=None, segment_start=None, status='legacy')
        if not isinstance(metadata, dict):
            metadata = dict(status='legacy')
        metadata = {k: metadata.get(k) for k in ('run_id', 'created_at', 'video_id', 'segment_start', 'end_timestamp', 'status', 'calibrated')}
        metadata['run_id'] = folder.name
        metadata['active'] = folder.name == service.state().get('run_id')
        metadata['available'] = {kind: (folder / (kind + '.csv')).is_file() for kind in ('vehicles', 'traffic_statistics', 'events', 'lane_statistics')}
        items.append(metadata)
    return dict(items=items, total=len(folders), offset=offset, limit=limit)


class SnapshotFileResponse(FileResponse):
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            Path(self.path).unlink(missing_ok=True)


@app.get('/api/export/{run_id}/{kind}')
def export(run_id: str, kind: str):
    if not re.fullmatch(r'\d{8}-\d{6}-[a-f0-9]{6}', run_id) or kind not in ('vehicles', 'traffic_statistics', 'events', 'lane_statistics'):
        raise HTTPException(400, '无效导出类型')
    path = DATA / 'runs' / run_id / (kind+'.csv')
    if not path.is_file():
        raise HTTPException(404, '暂无导出数据，请先开始分析')
    with tempfile.NamedTemporaryFile(prefix='twin-export-', suffix='.csv', delete=False) as temporary:
        snapshot_path = Path(temporary.name)
    try:
        processor = service.processor
        if processor and processor.exporter.directory == path.parent:
            processor.exporter.snapshot(kind, snapshot_path)
        else:
            shutil.copyfile(path, snapshot_path)
    except Exception:
        snapshot_path.unlink(missing_ok=True)
        raise
    return SnapshotFileResponse(snapshot_path, filename=f'{run_id}-{kind}.csv', media_type='text/csv')


def read_report(run_id):
    processor = service.processor
    exporter = processor.exporter if processor else None
    with snapshot_run(DATA, run_id, exporter) as directory:
        return build_report(directory, run_id)


def feature_error(exc):
    raise HTTPException(404 if isinstance(exc, FileNotFoundError) else 400, str(exc)) from exc


@app.get('/api/runs/{run_id}/report')
def analysis_report(run_id: str):
    try:
        return read_report(run_id)
    except (ValueError, FileNotFoundError) as exc:
        feature_error(exc)


@app.get('/api/runs/{run_id}/report.html', response_class=HTMLResponse)
def printable_report(run_id: str, download: bool = False):
    try:
        headers = {'Content-Disposition': f'attachment; filename="{run_id}-report.html"'} if download else {}
        return HTMLResponse(report_html(read_report(run_id)), headers=headers)
    except (ValueError, FileNotFoundError) as exc:
        feature_error(exc)


@app.get('/api/runs/{run_id}/compare/{other_id}')
def compare_run(run_id: str, other_id: str):
    try:
        return compare_reports(read_report(run_id), read_report(other_id))
    except (ValueError, FileNotFoundError) as exc:
        feature_error(exc)


@app.get('/api/runs/{run_id}/events')
def run_events(run_id: str, offset: int = 0, limit: int = 50):
    try:
        processor = service.processor
        if processor and processor.exporter.run_id == run_id:
            with processor.exporter.lock:
                processor.exporter.flush()
                return list_events(DATA, run_id, offset, limit)
        return list_events(DATA, run_id, offset, limit)
    except (ValueError, FileNotFoundError) as exc:
        feature_error(exc)


@app.get('/api/runs/{run_id}/events/{event_id}')
def evidence_detail(run_id: str, event_id: str):
    try:
        return event_detail(DATA, run_id, event_id)
    except (ValueError, FileNotFoundError) as exc:
        feature_error(exc)


@app.get('/api/runs/{run_id}/events/{event_id}/screenshot')
def event_screenshot(run_id: str, event_id: str):
    try:
        _, folder = evidence_directory(DATA, run_id, event_id)
        path = folder / 'screenshot.jpg'
        if not path.is_file():
            raise FileNotFoundError('事件截图不可用')
        return FileResponse(path, media_type='image/jpeg')
    except (ValueError, FileNotFoundError) as exc:
        feature_error(exc)


@app.get('/api/runs/{run_id}/events/{event_id}/source')
def event_source(run_id: str, event_id: str):
    try:
        detail = event_detail(DATA, run_id, event_id)
        path, reason = source_path(DATA, detail.get('source') or {})
        if path is None:
            raise FileNotFoundError(reason)
        return FileResponse(path)
    except (ValueError, FileNotFoundError) as exc:
        feature_error(exc)


class EventReview(BaseModel):
    status: Literal['pending', 'confirmed', 'false_positive']
    note: str = Field(default='', max_length=1000)


@app.post('/api/runs/{run_id}/events/{event_id}/review')
def review_event(run_id: str, event_id: str, payload: EventReview):
    try:
        return save_review(DATA, run_id, event_id, payload.status, payload.note)
    except (ValueError, FileNotFoundError) as exc:
        feature_error(exc)


@app.get('/api/camera-templates')
def saved_templates():
    return dict(items=camera_templates.list_templates(DATA))


@app.post('/api/camera-templates')
async def save_template(payload: TemplateCreate):
    try:
        async with service.lock:
            service.check_target(payload)
            return camera_templates.create_template(DATA, service, payload.name, payload.note)
    except StaleVideoError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        feature_error(exc)


@app.post('/api/camera-templates/{template_id}/rename')
async def rename_template(template_id: str, payload: TemplateRename):
    try:
        async with service.lock:
            return camera_templates.rename_template(DATA, template_id, payload.revision, payload.name, payload.note)
    except camera_templates.TemplateConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        feature_error(exc)


@app.post('/api/camera-templates/{template_id}/delete')
async def delete_template(template_id: str, payload: TemplateRevision):
    try:
        async with service.lock:
            camera_templates.delete_template(DATA, template_id, payload.revision)
            return dict(deleted=True)
    except camera_templates.TemplateConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        feature_error(exc)


@app.post('/api/camera-templates/{template_id}/preview')
async def preview_template(template_id: str, payload: TemplatePreview):
    try:
        async with service.lock:
            service.check_target(payload)
            return camera_templates.preview_template(DATA, service, template_id, payload.template_revision)
    except (camera_templates.TemplateConflict, StaleVideoError) as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        feature_error(exc)


@app.post('/api/camera-templates/{template_id}/apply')
async def apply_template(template_id: str, payload: TemplateApply):
    try:
        async with service.lock:
            service.check_target(payload)
            with camera_templates.template_transaction(DATA, template_id, payload.template_revision):
                preview = camera_templates.preview_template(DATA, service, template_id, payload.template_revision)
                if not preview['applicable'] or not payload.geometry_confirmed:
                    raise ValueError('请确认同一机位视野与当前几何；宽高比不匹配时须重新绘制')
                if payload.copy_scale and (not payload.scale_confirmed or not preview['calibration']):
                    raise ValueError('复制实测尺度需要模板已标定且单独确认同机位同视野及实际尺寸仍有效')
                calibration = preview['calibration'] if payload.copy_scale else None
                scene = SceneInput(**preview['scene'], **(calibration or {}), video_token=payload.video_token, scene_revision=payload.scene_revision)
                provenance = dict(template_id=template_id, template_revision=payload.template_revision,
                                  source=preview['source'], geometry_confirmed=True, scale_copied=payload.copy_scale,
                                  scale_confirmed=payload.scale_confirmed if payload.copy_scale else False,
                                  applied_at=camera_templates.now())
                await service.save_scene_locked(scene, provenance)
                return service.state()
    except (camera_templates.TemplateConflict, StaleVideoError) as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        feature_error(exc)


def active_exporter(run_id):
    processor = service.processor
    return processor.exporter if processor and processor.exporter.run_id == run_id and processor.exporter.metadata.get('status') == 'recording' else None


def annotation_error(exc):
    if isinstance(exc, annotations.AnnotationConflict):
        raise HTTPException(409, str(exc)) from exc
    feature_error(exc)


@app.get('/api/runs/{run_id}/annotation-context')
def annotation_context(run_id: str):
    try:
        return annotations.get_context(DATA, run_id, active_exporter(run_id))
    except (ValueError, FileNotFoundError, OSError) as exc:
        annotation_error(exc)


@app.get('/api/runs/{run_id}/source')
def run_original_source(run_id: str):
    try:
        directory = annotations.run_directory(DATA, run_id)
        metadata = annotations.read_json(directory / 'run.json', {})
        path, reason = source_path(DATA, metadata)
        if not path:
            raise FileNotFoundError(reason)
        return FileResponse(path)
    except (ValueError, FileNotFoundError, OSError) as exc:
        annotation_error(exc)


@app.get('/api/runs/{run_id}/observations')
def run_observations(run_id: str, seconds: float):
    try:
        return annotations.observations(DATA, run_id, seconds, active_exporter(run_id))
    except (ValueError, FileNotFoundError, OSError) as exc:
        annotation_error(exc)


@app.get('/api/runs/{run_id}/annotations')
def run_annotations(run_id: str):
    try:
        return annotations.load_annotations(DATA, run_id, active_exporter(run_id))
    except (ValueError, FileNotFoundError, OSError) as exc:
        annotation_error(exc)


@app.post('/api/runs/{run_id}/annotations')
def save_run_annotations(run_id: str, payload: annotations.AnnotationSave):
    try:
        return annotations.save_annotations(DATA, run_id, payload, active_exporter(run_id))
    except (ValueError, FileNotFoundError, OSError) as exc:
        annotation_error(exc)


@app.post('/api/runs/{run_id}/evaluate')
def evaluate_run_annotations(run_id: str, payload: annotations.EvaluationRequest):
    try:
        return annotations.evaluate_annotations(DATA, run_id, payload.expected_revision, payload.tolerance_seconds, active_exporter(run_id))
    except (ValueError, FileNotFoundError, OSError, KeyError, TypeError) as exc:
        annotation_error(ValueError('评测数据不可用：' + str(exc)) if not isinstance(exc, (ValueError, OSError)) else exc)


@app.get('/api/runs/{run_id}/annotations/download')
def download_annotations(run_id: str, revision: int | None = None):
    try:
        value = annotations.load_annotations(DATA, run_id, active_exporter(run_id))
        if not value['saved']:
            raise FileNotFoundError('尚无已保存人工文档')
        if revision is not None and revision != value['document']['revision']:
            raise annotations.AnnotationConflict('下载版本已改变，请重新打开人工文档')
        from fastapi.responses import JSONResponse
        return JSONResponse(value['document'], headers={'Content-Disposition': f'attachment; filename="{run_id}-annotations-r{value["document"]["revision"]}.json"'})
    except (ValueError, FileNotFoundError, OSError) as exc:
        annotation_error(exc)


@app.get('/api/runs/{run_id}/evaluation/download')
def download_evaluation(run_id: str, revision: int | None = None):
    try:
        value = annotations.load_annotations(DATA, run_id, active_exporter(run_id))
        if not value['result']:
            raise FileNotFoundError('尚无保存的评测结果')
        if value['result_stale'] or (revision is not None and revision != value['result']['annotation_revision']):
            raise annotations.AnnotationConflict('结果对应旧标注版本，请重新评测后下载')
        from fastapi.responses import JSONResponse
        return JSONResponse(value['result'], headers={'Content-Disposition': f'attachment; filename="{run_id}-evaluation-r{value["result"]["annotation_revision"]}.json"'})
    except (ValueError, FileNotFoundError, OSError) as exc:
        annotation_error(exc)


@app.websocket('/ws')
async def websocket(ws: WebSocket):
    if not trusted_origin(ws.headers.get('origin'), ws.headers.get('host', '')):
        await ws.close(code=1008)
        return
    await ws.accept()
    last = -1
    receive_task = asyncio.create_task(ws.receive())
    try:
        while True:
            if receive_task.done():
                if receive_task.result()['type'] == 'websocket.disconnect':
                    break
                receive_task = asyncio.create_task(ws.receive())
            if service.revision != last:
                data = service.state()
                last = data['revision']
                await ws.send_json(data)
            await asyncio.sleep(.025)
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass
    finally:
        receive_task.cancel()
        with suppress(asyncio.CancelledError, RuntimeError, WebSocketDisconnect):
            await receive_task


# The built React application is served by the backend, enabling one-command startup.
dist = ROOT / 'frontend' / 'dist'
if dist.exists():
    app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
else:
    @app.get('/', response_class=HTMLResponse)
    def frontend_not_built():
        return HTMLResponse(
            '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>隧道交通数字孪生</title>'
            '<body style="font-family:system-ui;line-height:1.6;max-width:40rem;margin:2rem auto">'
            '<h1>前端尚未构建</h1><p>API 与 <a href="/docs">/docs</a> 可用。请运行 '
            '<code>./scripts/setup.sh</code> 或 <code>npm --prefix frontend run build</code> 生成 '
            '<code>frontend/dist</code> 后刷新本页。</p>'
            '<p>开发模式可在两个终端分别启动后端与 <code>npm --prefix frontend run dev</code>（Vite 5173）。</p></body></html>'
        )
