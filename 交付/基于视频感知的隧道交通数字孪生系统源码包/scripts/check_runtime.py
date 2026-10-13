"""Isolated real HTTP/WS and shutdown check; never reads user calibration/runs."""
import asyncio
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def main():
    with tempfile.TemporaryDirectory(prefix='twin-runtime-') as temporary:
        data = Path(temporary)
        (data / 'videos').mkdir()
        writer = cv2.VideoWriter(str(data / 'videos/demo.mp4'), cv2.VideoWriter_fourcc(*'mp4v'), 10, (160, 96))
        if not writer.isOpened():
            raise RuntimeError('测试视频编码器不可用')
        for _ in range(12):
            writer.write(np.zeros((96, 160, 3), dtype=np.uint8))
        writer.release()
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        env = {**os.environ, 'TWIN_DATA_DIR': str(data)}
        with (data / 'server.log').open('w+') as log:
            process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                for _ in range(150):
                    if process.poll() is not None:
                        raise RuntimeError('测试服务启动失败')
                    try:
                        with urllib.request.urlopen(origin + '/api/health', timeout=.5) as response:
                            assert json.load(response)['ok']
                            break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError('测试服务启动超时')

                async def check():
                    from websockets.asyncio.client import connect
                    async with connect(f'ws://127.0.0.1:{port}/ws', origin=origin) as ws:
                        state = json.loads(await asyncio.wait_for(ws.recv(), 5))
                        assert state['video']['frames'] == 12 and state['calibration'] is None
                        assert state['image'].startswith('data:image/jpeg;base64,')
                        assert state['video_token'] and state['session_id']
                        assert state['status'] == 'ready' and state.get('run_id') is None
                    print('HTTP + trusted-origin idle WebSocket: PASS')

                asyncio.run(check())
                process.send_signal(signal.SIGINT)
                process.wait(timeout=8)
                log.seek(0)
                output = log.read()
                assert process.returncode == 0, output
                assert 'Application shutdown complete' in output, output
                assert not list((data / 'runs').iterdir())
                print('Graceful shutdown + isolated data: PASS')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()


if __name__ == '__main__':
    main()
