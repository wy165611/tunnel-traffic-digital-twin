"""Limits for the local browser boundary and streamed multipart input."""
import os
from urllib.parse import urlsplit
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse

MAX_VIDEO_BYTES = 2 * 1024**3


def trusted_origin(origin, host):
    if not origin or origin == 'null':
        return False
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    if parsed.scheme not in ('http', 'https') or parsed.path or parsed.query or parsed.fragment or parsed.username:
        return False
    allowed = {f'http://{host}', f'https://{host}',
               'http://127.0.0.1:5173', 'http://localhost:5173'}
    allowed.update(x.strip() for x in os.environ.get('TWIN_ALLOWED_ORIGINS', '').split(',') if x.strip())
    return origin in allowed


class UploadBodyLimit:
    def __init__(self, app, max_bytes=MAX_VIDEO_BYTES + 1024**2):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('path') != '/api/video/upload':
            return await self.app(scope, receive, send)
        error = JSONResponse({'detail': '视频上传请求超过大小限制（视频最大 2 GB）'}, status_code=413)
        length = dict(scope.get('headers', [])).get(b'content-length')
        if length:
            try:
                if int(length) > self.max_bytes:
                    return await error(scope, receive, send)
            except ValueError:
                return await JSONResponse({'detail': '无效请求长度'}, status_code=400)(scope, receive, send)
        total, exceeded, rejected = 0, False, False

        async def limited_receive():
            nonlocal total, exceeded
            message = await receive()
            if message['type'] == 'http.request':
                total += len(message.get('body', b''))
                if total > self.max_bytes:
                    exceeded = True
                    # The multipart parser closes all spooled files on this exception.
                    raise MultiPartException('视频上传请求超过大小限制')
            return message

        async def limited_send(message):
            nonlocal rejected
            if exceeded:
                if not rejected:
                    rejected = True
                    await error(scope, receive, send)
                return
            await send(message)

        await self.app(scope, limited_receive, limited_send)
