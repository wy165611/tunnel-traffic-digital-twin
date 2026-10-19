"""Optional best-effort event webhook; every failure is isolated from analysis."""
import json
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
import urllib.request


class WebhookNotifier:
    def __init__(self, config=None):
        config = config or {}
        url = str(config.get('webhook_url') or '').strip()
        parsed = urlparse(url)
        self.url = url if parsed.scheme in ('http', 'https') and parsed.netloc else ''
        self.enabled = bool(config.get('webhook_enabled')) and bool(self.url)
        self.timeout = self._number(config.get('webhook_timeout_seconds', 3.), 3., .2, 10.)
        self.retries = int(self._number(config.get('webhook_retries', 2), 2., 0, 5))
        self.cooldown = self._number(config.get('cooldown_seconds', 10.), 10., 0, 3600)
        self._last = {}
        self._lock = threading.Lock()

    @staticmethod
    def _number(value, default, low, high):
        try:
            return min(high, max(low, float(value)))
        except (TypeError, ValueError):
            return default

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
        thread = threading.Thread(target=self._send, args=(payload,), name='twin-event-webhook', daemon=True)
        thread.start()
        return thread

    def _send(self, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        for attempt in range(self.retries+1):
            try:
                request = urllib.request.Request(self.url, data=body,
                                                 headers={'Content-Type': 'application/json; charset=utf-8'},
                                                 method='POST')
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    response.read(1024)
                return
            except Exception:
                if attempt < self.retries:
                    time.sleep(min(2., .2*(attempt+1)))
        # A receiver outage must never stop video analysis or event capture.
