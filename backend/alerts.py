"""Optional best-effort event webhook; every failure is isolated from analysis."""
import json
import threading
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
        try:
            self.timeout = min(10., max(.2, float(config.get('webhook_timeout_seconds', 2.))))
        except (TypeError, ValueError):
            self.timeout = 2.

    def notify(self, event, run_id=None, video_id=None):
        if not self.enabled:
            return None
        payload = dict(type='traffic_event', run_id=run_id, video_id=video_id, event=event,
                       sent_at=datetime.now(timezone.utc).isoformat())
        thread = threading.Thread(target=self._send, args=(payload,), name='twin-event-webhook', daemon=True)
        thread.start()
        return thread

    def _send(self, payload):
        try:
            request = urllib.request.Request(self.url, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                                             headers={'Content-Type': 'application/json; charset=utf-8'}, method='POST')
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response.read(1024)
        except Exception:
            # A receiver outage must never stop video analysis or event capture.
            pass
