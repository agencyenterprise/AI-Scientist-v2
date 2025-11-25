#!/usr/bin/env python
"""Check status of recent runs"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

client = MongoClient(os.getenv("MONGODB_URL"))
db = client["ai-scientist"]
runs_collection = db["runs"]

recent = datetime.utcnow() - timedelta(hours=1)

failed_runs = list(runs_collection.find({
    "status": "FAILED",
    "createdAt": {"$gte": recent}
}))

queued_runs = list(runs_collection.find({
    "status": "QUEUED",
    "createdAt": {"$gte": recent}
}))

running_runs = list(runs_collection.find({
    "status": {"$in": ["RUNNING", "SCHEDULED"]},
    "createdAt": {"$gte": recent}
}))

print(f"Status of recent runs (last hour):")
print(f"  ✓ QUEUED: {len(queued_runs)}")
print(f"  🏃 RUNNING/SCHEDULED: {len(running_runs)}")
print(f"  ✗ FAILED: {len(failed_runs)}")

if failed_runs:
    print(f"\nFailed runs (you can retry with: python retry_failed_run.py --all):")
    for run in failed_runs:
        print(f"  - {run['_id']}")
        if 'error' in run:
            error = run['error'][:100] if len(run['error']) > 100 else run['error']
            print(f"    Error: {error}")





