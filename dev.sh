#!/bin/bash
# Start both backend and frontend for development
# Usage: ./dev.sh

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
  echo ""
  echo "Shutting down..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
  echo "Done."
}
trap cleanup EXIT INT TERM

# --- Backend ---
echo "==> Installing backend dependencies..."
cd "$ROOT/backend"
pip install -e ".[dev]" --quiet 2>/dev/null

echo "==> Starting backend on :8000..."
cd "$ROOT/backend"
python3 -m uvicorn cusco.main:app --reload --port 8000 &
BACKEND_PID=$!

# --- Frontend ---
echo "==> Installing frontend dependencies..."
cd "$ROOT/frontend"
npm install --silent 2>/dev/null

echo "==> Starting frontend on :5173..."
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "=================================="
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  Press Ctrl+C to stop both"
echo "=================================="

wait
