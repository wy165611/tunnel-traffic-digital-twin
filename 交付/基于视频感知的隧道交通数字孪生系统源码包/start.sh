#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo '请先执行 ./scripts/setup.sh 安装依赖。'
  exit 1
fi
if [ ! -f frontend/dist/index.html ]; then
  (cd frontend && npm run build)
fi
echo "隧道交通数字孪生：http://127.0.0.1:${TWIN_PORT:-8000}"
echo '按 Ctrl+C 停止；视频和所有分析 CSV 均保存在 backend/data。'
exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port "${TWIN_PORT:-8000}"
