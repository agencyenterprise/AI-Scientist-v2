#!/usr/bin/env python3
"""
Quick script to reset the last ideation request in MongoDB.
Changes it to: 5 ideas, 1 reflection, and sets status back to QUEUED.
"""

import os
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
if not MONGODB_URL:
    print("❌ MONGODB_URL not set!")
    exit(1)

client = MongoClient(MONGODB_URL)
db = client["ai-scientist"]
ideation_requests = db["ideation_requests"]

# Find the last ideation request
last_request = ideation_requests.find_one(sort=[("createdAt", -1)])

if not last_request:
    print("❌ No ideation requests found!")
    exit(1)

print(f"Found request: {last_request['_id']}")
print(f"  Status: {last_request.get('status')}")
print(f"  Reflections: {last_request.get('reflections')}")
print(f"  MaxNumGenerations: {last_request.get('maxNumGenerations', 1)}")

# Update it
result = ideation_requests.update_one(
    {"_id": last_request["_id"]},
    {
        "$set": {
            "status": "QUEUED",
            "reflections": 1,
            "maxNumGenerations": 5,
            "updatedAt": datetime.utcnow(),
            "claimedBy": None,
            "claimedAt": None,
            "startedAt": None
        },
        "$unset": {
            "ideas": "",
            "completedAt": "",
            "failedAt": "",
            "error": ""
        }
    }
)

if result.modified_count > 0:
    print("✅ Updated!")
    print("  Status: QUEUED")
    print("  Reflections: 1")
    print("  MaxNumGenerations: 5")
else:
    print("❌ Failed to update")
    exit(1)




