#!/usr/bin/env python3
"""Check WQ BRAIN task statuses."""
import sys, json, urllib.request

task_ids = sys.argv[1:]
if not task_ids:
    print("Usage: check_tasks.py <task_id> [task_id ...]")
    sys.exit(1)

for tid in task_ids:
    try:
        r = urllib.request.urlopen(f"http://localhost:8003/api/v1/tasks/{tid}")
        d = json.loads(r.read())
        s = d.get("status", "?")
        expr = d.get("params", {}).get("expression", "")[:80]
        neut = d.get("params", {}).get("neutralization", "?")
        line = f"{tid[:12]}: {s}"
        result = d.get("result")
        if result and isinstance(result, dict):
            wq = result.get("wq_brain", {})
            if wq:
                line += f"  Sh={wq.get('wq_sharpe','?')}  Ft={wq.get('wq_fitness','?')}  Ret={wq.get('wq_returns','?')}  TO={wq.get('wq_turnover','?')}  Rating={wq.get('wq_rating','?')}"
        print(line)
        print(f"  neut={neut}  expr={expr}")
    except Exception as e:
        print(f"{tid[:12]}: ERROR - {e}")
