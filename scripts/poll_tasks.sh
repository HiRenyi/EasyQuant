#!/bin/bash
# Poll multiple WQ BRAIN tasks until all complete
TASKS="$@"
while true; do
  all_done=true
  for tid in $TASKS; do
    STATUS=$(curl -s "http://localhost:8003/api/v1/tasks/$tid" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)
    echo "$(date +%H:%M:%S) $tid: $STATUS"
    if [ "$STATUS" != "completed" ] && [ "$STATUS" != "failed" ]; then
      all_done=false
    fi
  done
  if $all_done; then
    echo "=== ALL DONE ==="
    for tid in $TASKS; do
      echo "--- $tid ---"
      curl -s "http://localhost:8003/api/v1/tasks/$tid" | grep -o '"sharpe":[0-9.]*\|"fitness":[0-9.]*\|"turnover":[0-9.]*\|"returns":[0-9.]*\|"submittable":[a-z]*\|"long_short_sharpe":[0-9.]*\|"wq_fitness":[0-9.]*\|"rating":"[^"]*"'
    done
    break
  fi
  sleep 20
done
