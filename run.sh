#!/usr/bin/env bash
# Kayan prototype — API + console launcher (local development)
set -e
cd "$(dirname "$0")"

python3 -m pip install -r requirements.txt --quiet

if [ ! -d frontend/node_modules ]; then
  echo "Installing console dependencies (first run)..."
  (cd frontend && npm install --no-audit --no-fund)
fi

cat <<BANNER

  جمعية كيان — نظام إدارة المستفيدين

  Console (UI)  ->  http://localhost:3000
  API docs      ->  http://localhost:8000/docs
  OpenAPI spec  ->  http://localhost:8000/openapi.json

BANNER

# Start backend in background, console in foreground
PYTHONPATH=. uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null' EXIT INT TERM

(cd frontend && npm run dev -- --port 3000)
