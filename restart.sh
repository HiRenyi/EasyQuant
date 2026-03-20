#!/bin/bash
cd "$(dirname "$0")"

# Kill existing process on port 8002
PID=$(lsof -ti :8002)
if [ -n "$PID" ]; then
  echo "Stopping PID $PID..."
  kill "$PID"
  sleep 1
fi

# Build frontend
echo "Building frontend..."
cd frontend && npm run build --silent && cd ..

# Start server
echo "Starting QuantGPT on :8002..."
nohup python3 -m quantgpt --transport http > logs/server.log 2>&1 &
echo "PID: $!"
echo "Logs: logs/server.log"
