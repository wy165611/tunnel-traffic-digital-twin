import hashlib
import hmac
import json
from urllib.error import HTTPError
import backend.alerts as alerts
import backend.main as main
from test_api import client  # noqa: F401


class Response:
    status = 204
    def read(self, size=-1): return b''
    def __enter__(self): return self
    def __exit__(self, *args): return False


def deliver(notifier, event=None, **kwargs):
    thread = notifier.notify(event or dict(event='SPEEDING', vehicle_id=4, event_id='a' * 32), **kwargs)
    thread.join(2)
    assert not thread.is_alive()
    return thread


def notifier(**options):
    log = alerts.WebhookLog()
    config = {'webhook_enabled': True, 'webhook_url': 'http://127.0.0.1:9999/hook',
              'webhook_timeout_seconds': 1, 'webhook_retries': 0}
    config.update(options)
    return alerts.WebhookNotifier(config, delivery_log=log), log


def test_custom_headers_and_hmac_signature_cover_raw_body(monkeypatch):
    calls = []
    monkeypatch.setattr(alerts.urllib.request, 'urlopen', lambda request, timeout: calls.append(request) or Response())
    hook, log = notifier(webhook_headers={'X-Api-Key': 'gateway-token', 'X-Env': 'prod'},
                         webhook_hmac_secret='top-secret', webhook_hmac_header='X-Signature')
    deliver(hook, run_id='run-1', video_id='demo.mp4')
    request = calls[0]
    headers = {name.lower(): value for name, value in request.headers.items()}
    assert headers['x-api-key'] == 'gateway-token' and headers['x-env'] == 'prod'
    expected = hmac.new(b'top-secret', request.data, hashlib.sha256).hexdigest()
    assert headers['x-signature'] == 'sha256='+expected
    entry = log.query()['items'][0]
    assert entry['ok'] is True and entry['attempts'] == 1 and entry['run_id'] == 'run-1'
    assert entry['event_id'] == 'a' * 32 and entry['status_code'] == 204


def test_reserved_or_malformed_headers_are_ignored(monkeypatch):
    calls = []
    monkeypatch.setattr(alerts.urllib.request, 'urlopen', lambda request, timeout: calls.append(request) or Response())
    hook, _ = notifier(webhook_headers={'Content-Length': '1', 'Host': 'evil', 'Bad:Name': 'x',
                                        'X-Ok': 'yes', 'X-Inject': 'a\nb'})
    deliver(hook)
    headers = {name.lower(): value for name, value in calls[0].headers.items()}
    assert 'x-ok' in headers
    assert headers.get('content-length') != '1' and 'host' not in headers
    assert 'bad:name' not in headers and 'x-inject' not in headers


def test_failed_delivery_is_logged_with_attempts_without_secrets(monkeypatch):
    def explode(*args, **kwargs):
        raise OSError('receiver down at http://user:pass@host/secret')
    monkeypatch.setattr(alerts.urllib.request, 'urlopen', explode)
    monkeypatch.setattr(alerts.time, 'sleep', lambda seconds: None)
    hook, log = notifier(webhook_retries=2, webhook_hmac_secret='never-log-me',
                         webhook_headers={'Authorization': 'Bearer never-log-me'})
    deliver(hook)
    result = log.query(status='failed')
    entry = result['items'][0]
    assert result['total'] == 1 and entry['ok'] is False and entry['attempts'] == 3
    assert entry['error'] == 'OSError' and entry['status_code'] is None
    serialized = json.dumps(result, ensure_ascii=False)
    assert 'never-log-me' not in serialized and 'Bearer' not in serialized


def test_http_error_status_is_recorded(monkeypatch):
    def reject(request, timeout):
        raise HTTPError(request.full_url, 503, 'unavailable', {}, None)
    monkeypatch.setattr(alerts.urllib.request, 'urlopen', reject)
    hook, log = notifier()
    deliver(hook)
    entry = log.query()['items'][0]
    assert entry['ok'] is False and entry['status_code'] == 503 and entry['error'] == 'HTTP 503'


def test_webhook_log_api_filters_and_paginates(client, monkeypatch):
    c, _ = client
    log = alerts.WebhookLog()
    log.append(dict(event_id='ok', event='SPEEDING', ok=True, attempts=1, status_code=200))
    log.append(dict(event_id='bad', event='WRONG WAY', ok=False, attempts=3, status_code=None, error='TimeoutError'))
    monkeypatch.setattr(main, 'DELIVERY_LOG', log)
    body = c.get('/api/webhook-log').json()
    assert body['enabled'] is False and body['total'] == 2
    assert [item['event_id'] for item in body['items']] == ['bad', 'ok']
    failed = c.get('/api/webhook-log?status=failed').json()
    assert failed['total'] == 1 and failed['items'][0]['error'] == 'TimeoutError'
    assert c.get('/api/webhook-log?limit=0').status_code == 400
    assert c.get('/api/webhook-log?offset=-1').status_code == 400
