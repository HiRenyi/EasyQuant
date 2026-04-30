#!/usr/bin/env python3
"""Fetch all alphas from WQ BRAIN platform API."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantgpt.wq_brain_client import get_client

c = get_client("primary")
c.authenticate()
s = c._get_session()

r = s.get("https://api.worldquantbrain.com/users/self/alphas",
          params={"limit": 100, "offset": 0, "order": "-dateCreated"})
print(f"Status: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    if isinstance(data, dict) and "results" in data:
        alphas = data["results"]
    elif isinstance(data, list):
        alphas = data
    else:
        print(str(data)[:1000])
        sys.exit(0)

    print(f"Count: {len(alphas)}")
    print(f"{'id':12} {'created':22} {'status':12} expression")
    print("-" * 120)
    for a in alphas:
        aid = a.get("id", "?")
        created = str(a.get("dateCreated", "?"))[:19]
        status = a.get("status", "?")
        code = a.get("regular", {})
        if isinstance(code, dict):
            expr = code.get("code", "?")[:70]
        else:
            expr = str(code)[:70]
        print(f"{aid:12} {created:22} {status:12} {expr}")
else:
    print(r.text[:1000])
