#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
port="${TWIN_PORT:-8000}"
health_url="http://127.0.0.1:${port}/api/health"
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port "$port" --reload &
backend_pid=$!
trap 'kill "$backend_pid" 2>/dev/null || true' EXIT INT TERM
for _ in $(seq 1 60); do
  if curl -sf "$health_url" >/dev/null; then
    break
  fi
  if ! kill -0 "$backend_pid" 2>/dev/null; then
    echo "后端未能启动，请检查 .venv 与端口 ${port}。" >&2
    exit 1
  fi
  sleep 0.25
done
if ! curl -sf "$health_url" >/dev/null; then
  echo "后端健康检查超时：${health_url}" >&2
  exit 1
fi
cd frontend
npm run dev
