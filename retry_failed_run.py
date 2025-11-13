#!/usr/bin/env python
"""Reset a failed run back to QUEUED for retry"""

import sys
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

if len(sys.argv) < 2:
    print("Usage: python retry_failed_run.py <run_id>")
    print("\nOr run without args to reset ALL recent failed runs")
    sys.exit(1)

client = MongoClient(os.getenv("MONGODB_URL"))
db = client["ai-scientist"]
runs_collection = db["runs"]

if sys.argv[1] == "--all":
    # Reset all recently failed runs
    from datetime import timedelta
    recent = datetime.utcnow() - timedelta(hours=2)
    
    result = runs_collection.update_many(
        {
            "status": "FAILED",
            "createdAt": {"$gte": recent}
        },
        {
            "$set": {
                "status": "QUEUED",
                "claimedBy": None,
                "scheduledAt": None,
                "startedAt": None,
                "failedAt": None,
                "error": None,
                "updatedAt": datetime.utcnow()
            }
        }
    )
    print(f"✓ Reset {result.modified_count} failed runs back to QUEUED")
else:
    # Reset specific run
    run_id = sys.argv[1]
    
    run = runs_collection.find_one({"_id": run_id})
    if not run:
        print(f"✗ Run {run_id} not found")
        sys.exit(1)
    
    print(f"Found run: {run_id}")
    print(f"  Current status: {run.get('status')}")
    print(f"  Hypothesis: {run.get('hypothesisId')}")
    
    result = runs_collection.update_one(
        {"_id": run_id},
        {
            "$set": {
                "status": "QUEUED",
                "claimedBy": None,
                "scheduledAt": None,
                "startedAt": None,
                "failedAt": None,
                "error": None,
                "updatedAt": datetime.utcnow()
            }
        }
    )
    
    if result.modified_count > 0:
        print(f"✓ Reset run {run_id} to QUEUED - ready for retry!")
    else:
        print(f"⚠ Run was not modified (maybe already queued?)")


