#!/usr/bin/env python3
"""Enumerate the training runs an API key can see. Usage: list_org.py ENV_VAR [accessible|owned]"""
import os, sys, json
import tinker
from dotenv import load_dotenv

load_dotenv("/Users/mark/Desktop/AI/Pivotal/.env")
env = sys.argv[1]
scope = sys.argv[2] if len(sys.argv) > 2 else "accessible"
key = os.getenv(env) or sys.exit(f"{env} not set")

rc = tinker.ServiceClient(api_key=key).create_rest_client()

runs, offset = [], 0
while True:
    resp = rc.list_training_runs(limit=100, offset=offset, access_scope=scope).result()
    batch = resp.training_runs
    runs.extend(batch)
    total = getattr(resp.cursor, "total_count", None)
    offset += len(batch)
    if not batch or (total is not None and offset >= total):
        break

print(f"# {env} scope={scope}: {len(runs)} training runs\n")
for r in runs:
    d = r.model_dump() if hasattr(r, "model_dump") else dict(r)
    print(json.dumps(d, default=str))
