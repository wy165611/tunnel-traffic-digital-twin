#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload &
backend_pid=$!
trap 'kill "$backend_pid" 2>/dev/null || true' EXIT INT TERM
cd frontend
npm run dev
