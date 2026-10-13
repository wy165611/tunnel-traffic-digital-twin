import os
from pathlib import Path
import subprocess
import sys
import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize('option', ['--calibration', '--scene'])
def test_explicit_missing_cli_file_is_rejected_before_processing(tmp_path, option):
    video = tmp_path / 'exists.mp4'
    video.write_bytes(b'not decoded because argument validation must fail first')
    env = {**os.environ, 'TWIN_DATA_DIR': str(tmp_path / 'isolated-data')}
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/analyze.py'), '--video', str(video), option, str(tmp_path / 'missing.json')],
                            capture_output=True, text=True, timeout=15, env=env)
    assert result.returncode == 2 and option in result.stderr and 'missing.json' in result.stderr
    assert not list((tmp_path / 'isolated-data/runs').iterdir())


def test_malformed_cli_scene_is_rejected_without_loading_model_or_export(tmp_path):
    video = tmp_path / 'source.mp4'
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 10, (160, 96))
    writer.write(np.zeros((96, 160, 3), dtype=np.uint8))
    writer.release()
    scene = tmp_path / 'scene.json'
    scene.write_text('{ malformed JSON')
    env = {**os.environ, 'TWIN_DATA_DIR': str(tmp_path / 'isolated-data')}
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/analyze.py'), '--video', str(video), '--scene', str(scene)],
                            capture_output=True, text=True, timeout=15, env=env)
    assert result.returncode == 2 and 'error:' in result.stderr
    assert '权重缺失' not in result.stderr
    assert not list((tmp_path / 'isolated-data/runs').iterdir())
