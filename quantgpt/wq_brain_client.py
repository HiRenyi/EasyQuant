"""WorldQuant BRAIN API client.

Wraps the WQ BRAIN REST API for alpha simulation, quality checks, and
formal submission. Credentials are read from environment variables
WQ_BRAIN_EMAIL and WQ_BRAIN_PASSWORD.
"""

import logging
import os
import time
from typing import Callable

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.worldquantbrain.com"

SUBMIT_THRESHOLDS = {
    "sharpe": 1.25,
    "fitness": 1.0,
    "turnover_max": 0.7,
    "turnover_min": 0.01,
}

_POLL_INTERVAL = 10
_POLL_MAX_ATTEMPTS = 36
_CONCURRENT_BACKOFF = 30
_MAX_RETRIES = 5


def is_configured() -> bool:
    return bool(os.environ.get("WQ_BRAIN_EMAIL") and os.environ.get("WQ_BRAIN_PASSWORD"))


class WQBrainClient:
    def __init__(self, email: str | None = None, password: str | None = None):
        self.email = email or os.environ.get("WQ_BRAIN_EMAIL", "")
        self.password = password or os.environ.get("WQ_BRAIN_PASSWORD", "")
        self._session: httpx.Client | None = None

    def _get_session(self) -> httpx.Client:
        if self._session is None:
            self._session = httpx.Client(timeout=30.0)
        return self._session

    def close(self):
        if self._session:
            self._session.close()
            self._session = None

    def authenticate(self) -> bool:
        s = self._get_session()
        r = s.post(
            f"{API_BASE}/authentication",
            auth=(self.email, self.password),
        )
        if r.status_code == 429:
            retry = int(r.headers.get("Retry-After", "60"))
            logger.info(f"WQ auth rate-limited, waiting {retry}s")
            time.sleep(retry + 1)
            return self.authenticate()

        if r.status_code not in (200, 201):
            logger.error(f"WQ auth failed: HTTP {r.status_code}")
            return False

        data = r.json()
        if "inquiry" in data:
            logger.error("WQ auth requires biometric verification — log in via browser first")
            return False

        logger.info("WQ BRAIN authenticated")
        return True

    def get_user_info(self) -> dict:
        r = self._get_session().get(f"{API_BASE}/users/self")
        return r.json() if r.status_code == 200 else {}

    def simulate(
        self,
        expression: str,
        region: str = "USA",
        universe: str = "TOP3000",
        delay: int = 1,
        decay: int = 0,
        neutralization: str = "SUBINDUSTRY",
        truncation: float = 0.08,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> dict:
        s = self._get_session()
        payload = {
            "type": "REGULAR",
            "settings": {
                "instrumentType": "EQUITY",
                "region": region,
                "universe": universe,
                "delay": delay,
                "decay": decay,
                "neutralization": neutralization,
                "truncation": truncation,
                "pasteurization": "ON",
                "unitHandling": "VERIFY",
                "nanHandling": "OFF",
                "language": "FASTEXPR",
                "visualization": False,
            },
            "regular": expression,
        }

        for attempt in range(_MAX_RETRIES):
            r = s.post(f"{API_BASE}/simulations", json=payload)

            if r.status_code in (200, 201, 202):
                break

            if r.status_code == 429:
                detail = ""
                try:
                    detail = r.json().get("detail", "")
                except Exception:
                    pass

                if "CONCURRENT_SIMULATION_LIMIT" in detail:
                    wait = _CONCURRENT_BACKOFF * (attempt + 1)
                    logger.info(f"WQ concurrent limit, waiting {wait}s (attempt {attempt+1}/{_MAX_RETRIES})")
                    if progress_callback:
                        progress_callback(0, f"并发限制，等待 {wait}s（第 {attempt+1} 次重试）")
                    time.sleep(wait)
                    continue

                retry = int(r.headers.get("Retry-After", "60"))
                logger.info(f"WQ rate-limited, waiting {retry}s")
                if progress_callback:
                    progress_callback(0, f"速率限制，等待 {retry}s")
                time.sleep(retry + 1)
                continue

            return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:300]}"}
        else:
            return {"ok": False, "error": "WQ concurrent retry limit exceeded"}

        location = r.headers.get("Location", "")
        if not location:
            return {"ok": False, "error": "No Location header in response"}

        url = location if location.startswith("http") else f"{API_BASE}{location}"

        for i in range(_POLL_MAX_ATTEMPTS):
            r = s.get(url)
            if r.status_code != 200:
                time.sleep(_POLL_INTERVAL)
                continue

            data = r.json()
            status = data.get("status", "").upper()
            progress = data.get("progress", 0)

            if progress_callback:
                pct = int(progress * 100) if isinstance(progress, float) and progress <= 1 else int(progress)
                progress_callback(min(pct, 99), f"模拟进行中 ({pct}%)")

            if status in ("DONE", "COMPLETE"):
                alpha_raw = data.get("alpha", "")
                alpha_id = alpha_raw.split("/")[-1] if alpha_raw else None

                is_data = data.get("is", {})
                oos_data = data.get("oos", {})

                if alpha_id and not is_data:
                    alpha_detail = self._fetch_alpha(alpha_id)
                    is_data = alpha_detail.get("is", {})
                    oos_data = alpha_detail.get("oos", {})

                if progress_callback:
                    progress_callback(100, "模拟完成")

                return {
                    "ok": True,
                    "expression": expression,
                    "is": is_data,
                    "oos": oos_data,
                    "settings": data.get("settings", {}),
                    "alpha_id": alpha_id,
                    "simulation_id": data.get("id", ""),
                }
            elif status in ("ERROR", "FAILED"):
                return {"ok": False, "error": f"WQ simulation failed: {data.get('message', status)}"}

            time.sleep(_POLL_INTERVAL)

        return {"ok": False, "error": "WQ simulation polling timeout (6min)"}

    def _fetch_alpha(self, alpha_id: str) -> dict:
        r = self._get_session().get(f"{API_BASE}/alphas/{alpha_id}")
        return r.json() if r.status_code == 200 else {}

    def check_alpha(self, alpha_id: str) -> dict:
        r = self._get_session().get(f"{API_BASE}/alphas/{alpha_id}/check")
        if r.status_code == 200:
            return r.json()
        return {"error": f"HTTP {r.status_code}: {r.text[:300]}"}

    def submit_alpha(self, alpha_id: str) -> dict:
        r = self._get_session().post(f"{API_BASE}/alphas/{alpha_id}/submit")
        return {
            "status_code": r.status_code,
            "ok": r.status_code in (200, 201),
            "detail": r.text[:500],
        }

    def is_submittable(self, checks: dict) -> bool:
        is_checks = checks.get("is", {}).get("checks", [])
        fails = [c for c in is_checks if c.get("result") == "FAIL"]
        pending = [c for c in is_checks if c.get("result") == "PENDING"]
        return len(fails) == 0 and len(pending) == 0
