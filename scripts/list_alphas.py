#!/usr/bin/env python3
"""List all WQ BRAIN alphas from the API."""
import json, urllib.request

r = urllib.request.urlopen("http://localhost:8003/api/v1/wq-brain/submitted-alphas")
d = json.loads(r.read())
print(f"Total: {d['total']}")
print(f"{'alpha_id':12} {'Sh':>5} {'Ft':>5} {'neut':10} {'status':10} expression")
print("-" * 120)
for a in d["alphas"]:
    expr = a["expression"][:70]
    sh = a.get("sharpe", "?")
    ft = a.get("fitness", "?")
    print(f"{a['alpha_id']:12} {sh:>5} {ft:>5} {a['neutralization']:10} {a['status']:10} {expr}")
