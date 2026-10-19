import json
import backend.alerts as alerts


class Response:
    def __init__(self): self.data = b'ok'
    def read(self, size=-1): return self.data
    def __enter__(self): return self
    def __exit__(self, *args): return False


def test_webhook_disabled_by_default_and_rejects_unsafe_schemes(monkeypatch):
    calls = []
    monkeypatch.setattr(alerts.urllib.request, 'urlopen', lambda *args, **kwargs: calls.append(args) or Response())
    assert alerts.WebhookNotifier({}).notify(dict(event='SPEEDING')) is None
    assert alerts.WebhookNotifier({'webhook_enabled': True}).notify(dict(event='SPEEDING')) is None
    unsafe = alerts.WebhookNotifier({'webhook_enabled': True, 'webhook_url': 'file:///etc/passwd'})
    assert unsafe.notify(dict(event='SPEEDING')) is None
    assert calls == []


def test_webhook_posts_event_json_when_enabled(monkeypatch):
    calls = []
    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return Response()
    monkeypatch.setattr(alerts.urllib.request, 'urlopen', fake_urlopen)
    notifier = alerts.WebhookNotifier({'webhook_enabled': True, 'webhook_url': 'http://127.0.0.1:9999/hook',
                                       'webhook_timeout_seconds': 1})
    event = dict(event='CLOSE FOLLOWING', event_id='a' * 32, vehicle_id=3)
    thread = notifier.notify(event, run_id='run', video_id='demo.mp4')
    thread.join(2)
    assert not thread.is_alive()
    request, timeout = calls[0]
    assert request.full_url == 'http://127.0.0.1:9999/hook'
    assert request.get_method() == 'POST' and timeout == 1
    payload = json.loads(request.data)
    assert payload['type'] == 'traffic_event' and payload['run_id'] == 'run'
    assert payload['video_id'] == 'demo.mp4' and payload['event']['event_id'] == 'a' * 32


def test_webhook_failure_never_raises(monkeypatch):
    def explode(*args, **kwargs): raise OSError('receiver down')
    monkeypatch.setattr(alerts.urllib.request, 'urlopen', explode)
    notifier = alerts.WebhookNotifier({'webhook_enabled': True, 'webhook_url': 'https://example.invalid/hook'})
    thread = notifier.notify(dict(event='WRONG WAY'))
    thread.join(2)
    assert not thread.is_alive()
