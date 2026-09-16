#!/usr/bin/env bash
# Kayan Prototype — start everything locally with one command.
#
#   ./start.sh            backend (8000) + agent (8002) + console (3000)
#   ./start.sh --ngrok    also expose the backend via ngrok for the Meta WhatsApp webhook
#   ./start.sh --prod     run only the console, against the deployed Railway backend
#                         (shows real WhatsApp tickets; actions change PRODUCTION data)
#
# Sign-in: the first admin comes from ADMIN_EMAIL / ADMIN_PASSWORD (.env.local);
# locally it defaults to admin@kayan.local / kayan-admin-2026.
#
# Ctrl+C stops all services.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

BACKEND_PORT=8000
AGENT_PORT=8002
FRONTEND_PORT=3000
LOG_DIR="$PROJECT_DIR/logs"
PROD_API="https://kayan-prototype-production-f786.up.railway.app"
USE_NGROK=false
USE_PROD=false
for arg in "$@"; do
  case "$arg" in
    --ngrok) USE_NGROK=true ;;
    --prod) USE_PROD=true ;;
    *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

mkdir -p "$LOG_DIR"
PIDS=()

say()  { printf '\033[1;36m▸\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# Kill a process and all of its descendants (uvicorn --reload and npm spawn children).
kill_tree() {
  local pid=$1 child
  for child in $(pgrep -P "$pid" 2>/dev/null); do kill_tree "$child"; done
  kill "$pid" 2>/dev/null || true
}

cleanup() {
  trap - EXIT INT TERM
  [[ ${#PIDS[@]} -eq 0 ]] && return 0
  echo ""
  say "Stopping all services..."
  for pid in "${PIDS[@]:-}"; do [[ -n "$pid" ]] && kill_tree "$pid"; done
  wait 2>/dev/null || true
  say "All services stopped."
}
trap cleanup EXIT
trap 'cleanup; exit 0' INT TERM

port_busy() { lsof -iTCP:"$1" -sTCP:LISTEN -t >/dev/null 2>&1; }

wait_for() {  # wait_for <name> <url> <log>
  local name=$1 url=$2 log=$3
  for _ in $(seq 1 60); do
    curl -sf -o /dev/null "$url" && { say "$name is up"; return 0; }
    sleep 1
  done
  echo "---- last lines of $log ----" >&2
  tail -n 30 "$log" >&2
  fail "$name did not start (see $log)"
}

# ---------------------------------------------------------------- preflight
command -v python3 >/dev/null || fail "python3 is not installed"
command -v npm >/dev/null     || fail "npm (Node.js) is not installed"

if $USE_PROD; then
  port_busy "$FRONTEND_PORT" && fail "Port $FRONTEND_PORT is already in use. Free it with:  kill \$(lsof -ti tcp:$FRONTEND_PORT -sTCP:LISTEN)"
  [[ -d frontend/node_modules ]] || (cd frontend && npm install --no-audit --no-fund)
  curl -sf -m 15 -o /dev/null "$PROD_API/health" || fail "Railway backend is not reachable: $PROD_API"
  export BACKEND_URL="$PROD_API"
  printf '\033[1;33m! Console is connected to the PRODUCTION backend (%s).\n  Closing tickets, approving payments or recording decisions changes real data.\033[0m\n' "$PROD_API"
  if ! curl -sf -m 15 -o /dev/null "$PROD_API/openapi.json" -w '' || ! curl -s -m 15 "$PROD_API/openapi.json" | grep -q '"/auth/login"'; then
    printf '\033[1;33m! That backend does not have sign-in yet (not deployed), so the console cannot log in.\n  Use ./start.sh for local work, or deploy the backend first.\033[0m\n'
  fi
  say "Starting console on :$FRONTEND_PORT (log: logs/frontend.log)"
  (cd frontend && exec npm run dev -- --port "$FRONTEND_PORT") > "$LOG_DIR/frontend.log" 2>&1 &
  PIDS+=($!)
  wait_for "Console" "http://localhost:$FRONTEND_PORT/ar" "$LOG_DIR/frontend.log"
  printf '\n  Console   http://localhost:%s   (data: Railway)\n  Press Ctrl+C to stop\n\n' "$FRONTEND_PORT"
  while kill -0 "${PIDS[0]}" 2>/dev/null; do sleep 2; done
  exit 1
fi

for port in $BACKEND_PORT $AGENT_PORT $FRONTEND_PORT; do
  port_busy "$port" && fail "Port $port is already in use. Free it with:  kill \$(lsof -ti tcp:$port -sTCP:LISTEN)"
done

if [[ ! -x .venv/bin/python ]]; then
  say "Creating Python virtualenv (.venv)..."
  python3 -m venv .venv
fi
PY="$PROJECT_DIR/.venv/bin/python"
if ! "$PY" -c "import fastapi, uvicorn, httpx, openai, pydantic_settings, sqlite_vec" 2>/dev/null; then
  say "Installing Python dependencies..."
  "$PY" -m pip install --quiet -r requirements.txt -r agent/requirements.txt
fi

if [[ ! -d frontend/node_modules ]]; then
  say "Installing console dependencies (first run)..."
  (cd frontend && npm install --no-audit --no-fund)
fi

# The agent reads its settings from environment variables; load .env then .env.local.
for f in .env .env.local; do
  if [[ -f "$f" ]]; then set -a; source "$f"; set +a; say "Loaded $f"; fi
done
# Local development defaults (never used when the real values are set in .env.local).
if [[ -z "${AGENT_API_KEY:-}" ]]; then
  export AGENT_API_KEY="local-dev-agent-key"
  say "AGENT_API_KEY not set — using a local development key"
fi
if [[ -z "${ADMIN_EMAIL:-}" || -z "${ADMIN_PASSWORD:-}" ]]; then
  export ADMIN_EMAIL="${ADMIN_EMAIL:-admin@kayan.local}"
  export ADMIN_PASSWORD="${ADMIN_PASSWORD:-kayan-admin-2026}"
  LOCAL_ADMIN=true
fi

export PYTHONPATH="$PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export BACKEND_URL="http://localhost:$BACKEND_PORT"
export AGENT_URL="http://127.0.0.1:$AGENT_PORT"

# ---------------------------------------------------------------- start
say "Starting backend on :$BACKEND_PORT (log: logs/backend.log)"
"$PY" -m uvicorn backend.main:app --port "$BACKEND_PORT" --reload > "$LOG_DIR/backend.log" 2>&1 &
PIDS+=($!)

say "Starting agent on :$AGENT_PORT (log: logs/agent.log)"
"$PY" -m uvicorn agent.main:app --port "$AGENT_PORT" --reload > "$LOG_DIR/agent.log" 2>&1 &
PIDS+=($!)

say "Starting console on :$FRONTEND_PORT (log: logs/frontend.log)"
(cd frontend && exec npm run dev -- --port "$FRONTEND_PORT") > "$LOG_DIR/frontend.log" 2>&1 &
PIDS+=($!)

wait_for "Backend" "http://localhost:$BACKEND_PORT/health" "$LOG_DIR/backend.log"
wait_for "Agent"   "http://localhost:$AGENT_PORT/health"   "$LOG_DIR/agent.log"

# Seed demo data if the database is empty (fresh clone).
if "$PY" - "$BACKEND_PORT" <<'PYEOF'
import json, sys, urllib.request
counts = json.load(urllib.request.urlopen(f"http://localhost:{sys.argv[1]}/api"))["counts"]
sys.exit(0 if counts.get("beneficiaries", 0) == 0 else 1)
PYEOF
then
  say "Database is empty — seeding demo data..."
  curl -sf -X POST "http://localhost:$BACKEND_PORT/admin/seed" -o /dev/null && say "Seeded"
fi

wait_for "Console" "http://localhost:$FRONTEND_PORT/ar" "$LOG_DIR/frontend.log"

NGROK_URL=""
if $USE_NGROK; then
  command -v ngrok >/dev/null || fail "--ngrok given but ngrok is not installed"
  say "Starting ngrok -> :$BACKEND_PORT"
  ngrok http "$BACKEND_PORT" --log=stdout > "$LOG_DIR/ngrok.log" 2>&1 &
  PIDS+=($!)
  sleep 3
  NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | "$PY" -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null || echo "see http://localhost:4040")
fi

cat <<BANNER

==========================================
  Kayan Prototype is running
==========================================

  Console   http://localhost:$FRONTEND_PORT
  API docs  http://localhost:$BACKEND_PORT/docs
  Agent     http://localhost:$AGENT_PORT
BANNER
if $USE_NGROK; then
  echo "  Webhook   $NGROK_URL/webhook   (verify token: ${WHATSAPP_VERIFY_TOKEN:-kayan-verify-token})"
fi
if [[ "${LOCAL_ADMIN:-false}" == true ]]; then
  cat <<ADMIN

  Sign in   $ADMIN_EMAIL / $ADMIN_PASSWORD
            (local development account — set ADMIN_EMAIL and ADMIN_PASSWORD in .env.local to change)
ADMIN
fi
cat <<BANNER

  Logs      logs/backend.log · logs/agent.log · logs/frontend.log
  Press Ctrl+C to stop everything
==========================================
BANNER

# Exit (and clean up) as soon as any service dies.
while true; do
  for pid in "${PIDS[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      printf '\033[1;31m✗ A service exited unexpectedly — check logs/\033[0m\n' >&2
      exit 1
    fi
  done
  sleep 2
done
