"""Optional best-effort event webhook; every failure is isolated from analysis."""
import hashlib
import hmac
import json
import threading
import time
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlparse
import urllib.error
import urllib.request

RESERVED_HEADERS = {'content-length', 'host', 'content-type'}


class WebhookLog:
    """Newest-first in-memory delivery history; secrets and headers are never stored."""

    def __init__(self, maxlen=500):
        self.entries = deque(maxlen=maxlen)
        self.lock = threading.Lock()

    def append(self, entry):
        with self.lock:
            self.entries.appendleft(dict(entry))

    def query(self, limit=50, offset=0, status=None):
        with self.lock:
            items = list(self.entries)
        if status in ('success', 'failed'):
            expected = status == 'success'
            items = [item for item in items if bool(item.get('ok')) is expected]
        return dict(items=items[offset:offset+limit], total=len(items), offset=offset, limit=limit)


DELIVERY_LOG = WebhookLog()


class WebhookNotifier:
    def __init__(self, config=None, delivery_log=None):
        config = config or {}
        url = str(config.get('webhook_url') or '').strip()
        parsed = urlparse(url)
        self.url = url if parsed.scheme in ('http', 'https') and parsed.netloc else ''
        self.enabled = bool(config.get('webhook_enabled')) and bool(self.url)
        self.timeout = self._number(config.get('webhook_timeout_seconds', 3.), 3., .2, 10.)
        self.retries = int(self._number(config.get('webhook_retries', 2), 2., 0, 5))
        self.cooldown = self._number(config.get('cooldown_seconds', 10.), 10., 0, 3600)
        self.headers = self._headers(config.get('webhook_headers'))
        secret = config.get('webhook_hmac_secret')
        self.secret = str(secret).encode('utf-8') if secret else b''
        self.signature_header = str(config.get('webhook_hmac_header') or 'X-Twin-Signature').strip() or 'X-Twin-Signature'
        self.log = delivery_log or DELIVERY_LOG
        self._last = {}
        self._lock = threading.Lock()

    @staticmethod
    def _number(value, default, low, high):
        try:
            return min(high, max(low, float(value)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _headers(value):
        headers = {}
        if not isinstance(value, dict):
            return headers
        for name, raw in value.items():
            name, text = str(name or '').strip(), str(raw if raw is not None else '').strip()
            if not name or not text or name.lower() in RESERVED_HEADERS:
                continue
            if any(char in name for char in '\r\n:') or any(char in text for char in '\r\n'):
                continue
            headers[name] = text
        return headers

    def _signature(self, body):
        if not self.secret:
            return None
        return 'sha256='+hmac.new(self.secret, body, hashlib.sha256).hexdigest()

    def notify(self, event, run_id=None, video_id=None):
        if not self.enabled:
            return None
        key = (event.get('vehicle_id'), event.get('event'))
        now = time.monotonic()
        with self._lock:
            previous = self._last.get(key)
            if previous is not None and now-previous < self.cooldown:
                return None
            self._last[key] = now
        payload = dict(type='traffic_event', run_id=run_id, video_id=video_id, event=event,
                       sent_at=datetime.now(timezone.utc).isoformat())
        context = dict(event_id=event.get('event_id'), event=event.get('event'),
                       vehicle_id=event.get('vehicle_id'), run_id=run_id, video_id=video_id)
        thread = threading.Thread(target=self._send, args=(payload, context), name='twin-event-webhook', daemon=True)
        thread.start()
        return thread

    def _send(self, payload, context=None):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        entry = dict(context or {}, attempts=0, ok=False, status_code=None, error=None,
                     timestamp=datetime.now(timezone.utc).isoformat())
        try:
            for attempt in range(self.retries+1):
                entry['attempts'] = attempt+1
                headers = {'Content-Type': 'application/json; charset=utf-8', **self.headers}
                signature = self._signature(body)
                if signature:
                    headers[self.signature_header] = signature
                try:
                    request = urllib.request.Request(self.url, data=body, headers=headers, method='POST')
                    with urllib.request.urlopen(request, timeout=self.timeout) as response:
                        entry['status_code'] = getattr(response, 'status', None)
                        response.read(1024)
                    entry.update(ok=True, error=None)
                    break
                except urllib.error.HTTPError as exc:
                    entry.update(status_code=exc.code, error=f'HTTP {exc.code}')
                except Exception as exc:
                    entry['error'] = type(exc).__name__
                if attempt < self.retries:
                    time.sleep(min(2., .2*(attempt+1)))
        finally:
            # A receiver outage must never stop video analysis or event capture.
            self.log.append(entry)
