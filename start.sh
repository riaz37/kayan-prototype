#!/bin/bash
# Kayan Prototype — Start all services
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

echo "Starting Kayan Prototype..."
echo "Project dir: $PROJECT_DIR"

# Start backend on port 8000
echo "Starting backend on port 8000..."
cd "$PROJECT_DIR"
python3 -m uvicorn backend.main:app --port 8000 --reload &
BACKEND_PID=$!

# Start agent on port 8001
echo "Starting agent on port 8001..."
python3 -m uvicorn agent.main:app --port 8001 --reload &
AGENT_PID=$!

# Start ngrok on port 8001
echo "Starting ngrok on port 8001..."
ngrok http 8001 --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!
sleep 3

# Get ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null || echo "Check http://localhost:4040")

echo ""
echo "=========================================="
echo "  Kayan Prototype is running!"
echo "=========================================="
echo ""
echo "  Backend:   http://localhost:8000"
echo "  Agent:     http://localhost:8001"
echo "  Ngrok:     $NGROK_URL"
echo ""
echo "  Webhook URL for Meta: $NGROK_URL/webhook"
echo "  Verify token: kayan-verify-token"
echo ""
echo "  Press Ctrl+C to stop all services"
echo "=========================================="

# Cleanup on exit
cleanup() {
    echo ""
    echo "Stopping all services..."
    kill $BACKEND_PID $AGENT_PID $NGROK_PID 2>/dev/null
    wait $BACKEND_PID $AGENT_PID $NGROK_PID 2>/dev/null
    echo "All services stopped."
}
trap cleanup EXIT INT TERM

# Wait for all processes
wait
