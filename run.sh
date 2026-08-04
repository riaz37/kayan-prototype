#!/usr/bin/env bash
# Kayan prototype — backend + agent + console, for local development.
#
#   ./run.sh              backend :8001 · agent :8002 · console :3000
#   ./run.sh --no-agent   skip the LLM agent (no LLM endpoint needed)
#   ./run.sh --reseed     wipe and regenerate the demo data first
#   ./run.sh --tunnel     also expose the agent via ngrok (Meta webhook testing)
set -euo pipefail
cd "$(dirname "$0")"

WITH_AGENT=1
RESEED=0
TUNNEL=0
for arg in "$@"; do
  case "$arg" in
    --no-agent) WITH_AGENT=0 ;;
    --reseed)   RESEED=1 ;;
    --tunnel)   TUNNEL=1 ;;
    -h|--help)  sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

BACKEND_PORT=${BACKEND_PORT:-8001}
AGENT_PORT=${AGENT_PORT:-8002}
FRONTEND_PORT=${FRONTEND_PORT:-3000}

# --- python environment (uv if available, plain venv otherwise)
if [ ! -d .venv ]; then
  echo "Creating .venv ..."
  if command -v uv >/dev/null 2>&1; then uv venv .venv; else python3 -m venv .venv; fi
fi
PY=.venv/bin/python
if command -v uv >/dev/null 2>&1; then
  VIRTUAL_ENV="$PWD/.venv" uv pip install -q -r requirements.txt -r agent/requirements.txt
else
  $PY -m pip install -q -r requirements.txt -r agent/requirements.txt
fi

# --- console bundle
if [ ! -f frontend/dist/app.css ] || [ ! -f frontend/dist/vendor/react.js ]; then
  echo "Building the console UI (first run) ..."
  (cd frontend && ./build.sh)
fi

# --- demo data: seed on first run, or on --reseed
export PYTHONPATH="$PWD"
if [ "$RESEED" = "1" ] || [ ! -f data/kayan.db ]; then
  echo "Seeding demo data ..."
  $PY backend/seed_production.py >/dev/null
fi

PIDS=()
cleanup() {
  echo ""
  echo "Stopping ..."
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

$PY -m uvicorn backend.main:app --port "$BACKEND_PORT" --reload &
PIDS+=($!)

if [ "$WITH_AGENT" = "1" ]; then
  BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}" \
    $PY -m uvicorn agent.main:app --port "$AGENT_PORT" --reload &
  PIDS+=($!)
fi

(cd frontend && "../$PY" -m http.server "$FRONTEND_PORT" >/dev/null 2>&1) &
PIDS+=($!)

WEBHOOK_LINE=""
if [ "$TUNNEL" = "1" ]; then
  if command -v ngrok >/dev/null 2>&1; then
    ngrok http "$AGENT_PORT" --log=stdout >/tmp/kayan-ngrok.log 2>&1 &
    PIDS+=($!)
    sleep 3
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels \
      | $PY -c "import sys,json;print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null || echo "")
    if [ -n "$NGROK_URL" ]; then
      WEBHOOK_LINE="  Meta webhook ->  ${NGROK_URL}/webhook  (verify token: kayan-verify-token)"
    else
      WEBHOOK_LINE="  Meta webhook ->  check http://localhost:4040"
    fi
  else
    echo "ngrok not found — skipping --tunnel" >&2
  fi
fi

sleep 2
cat <<BANNER

  جمعية كيان — نظام إدارة المستفيدين

  Console      ->  http://localhost:${FRONTEND_PORT}
  API docs     ->  http://localhost:${BACKEND_PORT}/docs
  OpenAPI      ->  http://localhost:${BACKEND_PORT}/openapi.json
$([ "$WITH_AGENT" = "1" ] && echo "  Agent        ->  http://localhost:${AGENT_PORT}/health")
${WEBHOOK_LINE}

  The console talks to localhost:8001 automatically.
  Point it elsewhere with ?api=https://your-backend

  Ctrl+C to stop.

BANNER

wait
