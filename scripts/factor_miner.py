"""Factor mining utilities — submit expressions to QuantGPT server and parse results.

Stateless utility library. The research loop is driven by the
factor-mine skill (SKILL.md), not by this file.

Usage from skill (via bash):
  python3 -c "
  import sys; sys.path.insert(0, '.')
  from scripts.factor_miner import evaluate
  import json
  result = evaluate('http://localhost:8003', 'rank(...)', {...})
  print(json.dumps(result, ensure_ascii=False) if result else '{\"error\": \"failed\"}')
  "
"""

import json
import re
import time
from dataclasses import dataclass
from typing import Optional

import requests

DEFAULT_SERVER = "http://localhost:8003"


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
    for attempt in range(6):
        try:
            r = requests.post(f"{server}/api/v1/auto_backtest", json=payload, timeout=10)
            if r.status_code == 202:
                return r.json()["task_id"]
            if r.status_code in (429, 503):
                time.sleep(12 + attempt * 12)
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


def batch_evaluate(
    server: str,
    expressions: list[str],
    params: dict,
    max_concurrent: int = 10,
    timeout: int = 600,
) -> list[dict]:
    """Submit multiple expressions concurrently, poll all, return sorted by fitness.

    Phase 1: submit all with retry waves (up to 3 waves for failures).
    Phase 2: poll all concurrently.
    Returns list of factor dicts sorted by fitness descending.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    task_map: dict[str, str] = {}
    failed_exprs: list[str] = []

    for wave in range(3):
        batch = expressions if wave == 0 else failed_exprs
        if not batch:
            break
        failed_exprs = []

        with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
            futures = {pool.submit(submit_task, server, expr, params): expr for expr in batch}
            for fut in as_completed(futures):
                expr = futures[fut]
                try:
                    tid = fut.result()
                    if tid:
                        task_map[expr] = tid
                    else:
                        failed_exprs.append(expr)
                except Exception:
                    failed_exprs.append(expr)

        if failed_exprs and wave < 2:
            time.sleep(5 * (wave + 1))

    results: list[dict] = []

    def _poll_and_parse(expr: str, tid: str) -> Optional[dict]:
        raw = poll_task(server, tid, timeout)
        f = parse_result(raw, expr, params)
        return f.__dict__ if f else None

    with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
        futures = {pool.submit(_poll_and_parse, expr, tid): expr for expr, tid in task_map.items()}
        for fut in as_completed(futures):
            try:
                r = fut.result()
                if r:
                    results.append(r)
            except Exception:
                pass

    results.sort(key=lambda x: x.get("fitness", 0), reverse=True)
    return results
