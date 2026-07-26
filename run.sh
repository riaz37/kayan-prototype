#!/usr/bin/env bash
# Kayan prototype — API + console launcher
set -e
cd "$(dirname "$0")"

python3 -m pip install -r requirements.txt --quiet

if [ ! -f frontend/dist/app.css ]; then
  echo "Building the console UI (first run)..."
  (cd frontend && ./build.sh)
fi

echo "Regenerating seed data..."
python3 scripts/generate_seed.py > /dev/null

cat <<BANNER

  جمعية كيان — نظام إدارة المستفيدين

  Console (UI)  ->  http://localhost:8000/app/
  API docs      ->  http://localhost:8000/docs
  OpenAPI spec  ->  http://localhost:8000/openapi.json

BANNER
PYTHONPATH=. uvicorn backend.main:app --reload --port 8000
