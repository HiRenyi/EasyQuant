"""Factor mining utilities — submit expressions to QuantGPT server and parse results.

Stateless utility library. The research loop is driven by the
factor-mine skill (SKILL.md), not by this file.

Usage from skill (via bash):
  python3 -c "
  import sys; sys.path.insert(0, '.')
  from scripts.factor_miner import evaluate
  import json
  result = evaluate('https://quantgpt.online', 'rank(...)', {...})
  print(json.dumps(result, ensure_ascii=False) if result else '{\"error\": \"failed\"}')
  "
"""

import json
import re
import time
from dataclasses import dataclass
from typing import Optional

import requests

DEFAULT_SERVER = "https://quantgpt.online"


@dataclass
class Factor:
    expression: str
    fitness: float = 0.0
    sharpe: float = 0.0
    returns: float = 0.0
    turnover: float = 0.0
    rating: str = "?"
    universe: str = ""
    wq_rating: str = ""
    submittable: bool = False
    ic: float = 0.0
    timestamp: str = ""


def normalize(expr: str) -> str:
    return re.sub(r"\s+", "", expr.lower())


def check_health(server: str = DEFAULT_SERVER) -> dict:
    r = requests.get(f"{server}/api/v1/health", timeout=5)
    return r.json()


def submit_task(server: str, expression: str, params: dict) -> Optional[str]:
    payload = {"prompt": expression, **params}
    for attempt in range(3):
        try:
            r = requests.post(f"{server}/api/v1/auto_backtest", json=payload, timeout=10)
            if r.status_code == 202:
                return r.json()["task_id"]
            if r.status_code in (429, 503):
                time.sleep(20 + attempt * 15)
                continue
            return None
        except Exception:
            time.sleep(10)
    return None


def poll_task(server: str, task_id: str, timeout: int = 600) -> Optional[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{server}/api/v1/tasks/{task_id}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") in ("completed", "failed"):
                    return data
            time.sleep(5)
        except Exception:
            time.sleep(8)
    return None


def submit_and_poll(server: str, expression: str, params: dict, timeout: int = 600) -> Optional[dict]:
    task_id = submit_task(server, expression, params)
    if not task_id:
        return None
    return poll_task(server, task_id, timeout)


def parse_result(result: dict, expression: str, params: dict) -> Optional[Factor]:
    if not result or result.get("status") != "completed":
        return None
    try:
        r = result.get("result", {})
        bs = r.get("backtest_summary", {})
        interp = r.get("interpretation", {})
        wq = r.get("wq_brain", {})
        is_tests = wq.get("wq_is_tests", {})
        return Factor(
            expression=expression,
            fitness=round(wq.get("wq_fitness", bs.get("wq_fitness", 0)), 3),
            sharpe=round(wq.get("wq_sharpe", bs.get("long_short_sharpe", 0)), 3),
            returns=round(wq.get("wq_returns", bs.get("long_short_annual", 0)), 4),
            turnover=round(wq.get("wq_turnover", bs.get("turnover", 0)), 3),
            rating=interp.get("rating", "?"),
            universe=params.get("universe", "?"),
            wq_rating=wq.get("wq_rating", "?"),
            submittable=wq.get("submittable", False),
            ic=round(bs.get("rank_ic_mean", 0), 4),
        )
    except Exception:
        return None


def evaluate(server: str, expression: str, params: dict) -> Optional[dict]:
    """Submit, poll, parse — return dict of factor metrics or None."""
    result = submit_and_poll(server, expression, params)
    factor = parse_result(result, expression, params)
    if factor:
        return factor.__dict__
    return None
