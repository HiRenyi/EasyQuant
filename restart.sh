#!/bin/bash
cd "$(dirname "$0")"

# Kill existing process on port 8002
PIDS=$(lsof -ti :8002)
if [ -n "$PIDS" ]; then
  echo "Stopping PIDs: $(echo $PIDS | tr '\n' ' ')..."
  echo "$PIDS" | xargs kill -9
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
