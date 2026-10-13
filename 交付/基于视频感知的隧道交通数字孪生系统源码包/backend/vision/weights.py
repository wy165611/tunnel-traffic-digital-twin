"""Pinned local weights. Verification happens once before any deserialization."""
import hashlib
import json
from pathlib import Path
from backend.settings import DATA, ROOT


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verified_weight(filename):
    records = json.loads((ROOT / 'models.json').read_text(encoding='utf-8'))
    record = next((x for x in records if x['filename'] == filename), None)
    if not record:
        raise ValueError('模型未登记在 models.json 中')
    path = DATA / 'models' / filename
    if not path.is_file():
        raise ValueError('预训练权重缺失，请运行 .venv/bin/python scripts/download_models.py')
    if sha256_file(path) != record['sha256']:
        raise ValueError('模型权重校验失败，请重新运行 .venv/bin/python scripts/download_models.py')
    return path
