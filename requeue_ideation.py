#!/usr/bin/env python3
"""
Requeue the ideation request for the most recent hypothesis
"""
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv(".env")
uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGODB_URL")

if not uri:
    print("❌ MongoDB URI not set!")
    exit(1)

client = MongoClient(uri)
db = client["ai-scientist"]

# Find the most recent hypothesis
hyp = db.hypotheses.find_one(
    {"_id": "018b08f0-ef2c-4da0-8f67-7b8dd7381aff"}
)

if not hyp:
    print("❌ Hypothesis not found!")
    exit(1)

print(f"Found hypothesis: {hyp.get('title')[:80]}")

# Reset the ideation status in the hypothesis
db.hypotheses.update_one(
    {"_id": hyp["_id"]},
    {
        "$set": {
            "ideation.status": "QUEUED",
            "ideation.ideas": [],
            "updatedAt": datetime.utcnow()
        },
        "$unset": {
            "ideation.startedAt": "",
            "ideation.completedAt": "",
            "ideation.error": ""
        }
    }
)

# Create a new ideation request
request_id = hyp["ideation"]["requestId"]
print(f"Resetting ideation request: {request_id}")

# Check if the ideation request exists
ideation_req = db.ideation_requests.find_one({"_id": request_id})

if ideation_req:
    print("Ideation request exists in ideation_requests collection, updating it...")
    db.ideation_requests.update_one(
        {"_id": request_id},
        {
            "$set": {
                "status": "QUEUED",
                "maxNumGenerations": 2,  # Generate 2 ideas
                "reflections": 5,  # 5 reflections for reliable finalization
                "updatedAt": datetime.utcnow()
            },
            "$unset": {
                "claimedBy": "",
                "claimedAt": "",
                "startedAt": "",
                "completedAt": "",
                "failedAt": "",
                "error": "",
                "ideas": "",
                "output": ""
            }
        }
    )
else:
    print("❌ Ideation request not found in ideation_requests collection!")
    print(f"   Looking for _id: {request_id}")
    exit(1)

print("\n✅ Ideation request reset to QUEUED")
print("   - maxNumGenerations: 2")
print("   - reflections: 5")
print("   - Ideas array cleared in MongoDB")
print("\n⚠️  IMPORTANT: Delete the existing JSON file on the pod to avoid duplicates:")
print(f"   rm /workspace/AI-Scientist-v2/ai_scientist/ideas/runtime/{request_id}.json")
print("\nThe pod worker will pick it up and you'll see REAL-TIME LOGS!")
print("\n⚠️  NOTE: reflections=5 gives the LLM enough rounds to search, refine, and finalize.")
print("   With 3 reflections, ideas often don't get finalized.")

