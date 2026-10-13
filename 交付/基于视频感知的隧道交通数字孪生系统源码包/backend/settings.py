from pathlib import Path
import os
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('TWIN_DATA_DIR', ROOT / 'backend' / 'data')).expanduser().resolve()
for name in ('videos', 'models', 'runs', 'calibrations'):
    (DATA / name).mkdir(parents=True, exist_ok=True)


def load_config():
    with (ROOT / 'config.yaml').open(encoding='utf-8') as f:
        return yaml.safe_load(f)
