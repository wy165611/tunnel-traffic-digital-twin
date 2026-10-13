"""All pipeline tests export into temporary storage, never the user's run history."""
import pytest


@pytest.fixture(autouse=True)
def isolated_exporter(tmp_path, monkeypatch):
    import backend.exporter as exporter
    data = tmp_path / 'isolated-exports'
    (data / 'runs').mkdir(parents=True)
    monkeypatch.setattr(exporter, 'DATA', data)
