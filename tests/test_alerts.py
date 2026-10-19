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
    calls = []
    def explode(*args, **kwargs):
        calls.append(1)
        raise OSError('receiver down')
    monkeypatch.setattr(alerts.urllib.request, 'urlopen', explode)
    monkeypatch.setattr(alerts.time, 'sleep', lambda seconds: None)
    notifier = alerts.WebhookNotifier({'webhook_enabled': True, 'webhook_url': 'https://example.invalid/hook'})
    thread = notifier.notify(dict(event='WRONG WAY', vehicle_id=1))
    thread.join(2)
    assert not thread.is_alive()
    assert len(calls) == 3  # one attempt plus the default two retries


def test_webhook_retries_transient_failures_then_succeeds(monkeypatch):
    calls = []
    def flaky(request, timeout):
        calls.append((request, timeout))
        if len(calls) == 1:
            raise TimeoutError('first attempt timed out')
        return Response()
    monkeypatch.setattr(alerts.urllib.request, 'urlopen', flaky)
    monkeypatch.setattr(alerts.time, 'sleep', lambda seconds: None)
    notifier = alerts.WebhookNotifier({'webhook_enabled': True, 'webhook_url': 'http://127.0.0.1:9999/hook',
                                       'webhook_retries': 2, 'webhook_timeout_seconds': 3})
    thread = notifier.notify(dict(event='SPEEDING', vehicle_id=2))
    thread.join(2)
    assert len(calls) == 2 and calls[0][1] == 3


def test_webhook_notification_cooldown_deduplicates_same_vehicle_event(monkeypatch):
    calls = []
    monkeypatch.setattr(alerts.urllib.request, 'urlopen', lambda request, timeout: calls.append(request) or Response())
    notifier = alerts.WebhookNotifier({'webhook_enabled': True, 'webhook_url': 'http://127.0.0.1:9999/hook',
                                       'cooldown_seconds': 10})
    first = notifier.notify(dict(event='SPEEDING', vehicle_id=7, event_id='a' * 32))
    assert first is not None
    first.join(2)
    assert notifier.notify(dict(event='SPEEDING', vehicle_id=7, event_id='b' * 32)) is None
    assert notifier.notify(dict(event='SPEEDING', vehicle_id=8, event_id='c' * 32)) is not None
    assert notifier.notify(dict(event='CLOSE FOLLOWING', vehicle_id=7, event_id='d' * 32)) is not None
    assert len(calls) == 3
