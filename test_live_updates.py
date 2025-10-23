#!/usr/bin/env python3
"""
Test script to simulate run updates and see live polling in the frontend.
Watch the browser console for update logs!
"""

import os
import sys
import time
from pymongo import MongoClient
from datetime import datetime

MONGODB_URL = os.environ.get("MONGODB_URL", "")

if not MONGODB_URL:
    print("❌ MONGODB_URL environment variable not set", file=sys.stderr)
    sys.exit(1)


def connect_mongodb():
    client = MongoClient(MONGODB_URL)
    try:
        client.admin.command("ping")
        print("✓ Connected to MongoDB\n")
        
        db_name = os.environ.get("MONGODB_DATABASE")
        
        if not db_name:
            if "/" in MONGODB_URL:
                parts = [p for p in MONGODB_URL.split("/") if p]
                if parts:
                    extracted = parts[-1].split("?")[0]
                    if extracted and not extracted.startswith("mongodb"):
                        db_name = extracted
        
        if not db_name:
            db_name = "ai_scientist"
        
        return client[db_name]
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}", file=sys.stderr)
        sys.exit(1)


def simulate_run_progress(db, run_id):
    """Simulate a run progressing through stages"""
    runs = db["runs"]
    stages_collection = db["stages"]
    
    print(f"\n{'='*60}")
    print(f"Simulating Run Progress: {run_id}")
    print(f"{'='*60}\n")
    print("👀 Watch your browser console for update logs!")
    print("   You should see: [Run xxxxxxxx] Status: ... | Stage: ... | Progress: ...\n")
    
    # Step 1: Set to RUNNING
    print("Step 1: Setting status to RUNNING...")
    runs.update_one(
        {"_id": run_id},
        {"$set": {
            "status": "RUNNING",
            "updatedAt": datetime.utcnow(),
            "pod": {
                "id": "test-pod-123",
                "instanceType": "A100"
            }
        }}
    )
    time.sleep(6)  # Wait for frontend to poll
    
    # Step 2: Start Stage_1
    print("Step 2: Starting Stage_1...")
    runs.update_one(
        {"_id": run_id},
        {"$set": {
            "currentStage": {"name": "Stage_1", "progress": 0},
            "updatedAt": datetime.utcnow()
        }}
    )
    stages_collection.update_one(
        {"_id": f"{run_id}-Stage_1"},
        {"$set": {
            "runId": run_id,
            "name": "Stage_1",
            "index": 0,
            "status": "RUNNING",
            "progress": 0,
            "startedAt": datetime.utcnow()
        }},
        upsert=True
    )
    time.sleep(6)
    
    # Step 3: Progress Stage_1 to 25%
    print("Step 3: Stage_1 → 25%...")
    runs.update_one(
        {"_id": run_id},
        {"$set": {
            "currentStage.progress": 0.25,
            "updatedAt": datetime.utcnow()
        }}
    )
    stages_collection.update_one(
        {"_id": f"{run_id}-Stage_1"},
        {"$set": {"progress": 0.25}}
    )
    time.sleep(6)
    
    # Step 4: Progress Stage_1 to 50%
    print("Step 4: Stage_1 → 50%...")
    runs.update_one(
        {"_id": run_id},
        {"$set": {
            "currentStage.progress": 0.5,
            "updatedAt": datetime.utcnow()
        }}
    )
    stages_collection.update_one(
        {"_id": f"{run_id}-Stage_1"},
        {"$set": {"progress": 0.5}}
    )
    time.sleep(6)
    
    # Step 5: Complete Stage_1
    print("Step 5: Stage_1 → COMPLETED...")
    runs.update_one(
        {"_id": run_id},
        {"$set": {
            "currentStage.progress": 1.0,
            "updatedAt": datetime.utcnow()
        }}
    )
    stages_collection.update_one(
        {"_id": f"{run_id}-Stage_1"},
        {"$set": {
            "progress": 1.0,
            "status": "COMPLETED",
            "completedAt": datetime.utcnow()
        }}
    )
    time.sleep(6)
    
    # Step 6: Start Stage_2
    print("Step 6: Starting Stage_2...")
    runs.update_one(
        {"_id": run_id},
        {"$set": {
            "currentStage": {"name": "Stage_2", "progress": 0},
            "updatedAt": datetime.utcnow()
        }}
    )
    stages_collection.update_one(
        {"_id": f"{run_id}-Stage_2"},
        {"$set": {
            "runId": run_id,
            "name": "Stage_2",
            "index": 1,
            "status": "RUNNING",
            "progress": 0,
            "startedAt": datetime.utcnow()
        }},
        upsert=True
    )
    time.sleep(6)
    
    # Step 7: Progress Stage_2 to 75%
    print("Step 7: Stage_2 → 75%...")
    runs.update_one(
        {"_id": run_id},
        {"$set": {
            "currentStage.progress": 0.75,
            "updatedAt": datetime.utcnow()
        }}
    )
    stages_collection.update_one(
        {"_id": f"{run_id}-Stage_2"},
        {"$set": {"progress": 0.75}}
    )
    time.sleep(6)
    
    # Step 8: Set to AUTO_VALIDATING
    print("Step 8: Setting status to AUTO_VALIDATING...")
    runs.update_one(
        {"_id": run_id},
        {"$set": {
            "status": "AUTO_VALIDATING",
            "updatedAt": datetime.utcnow()
        }}
    )
    stages_collection.update_one(
        {"_id": f"{run_id}-Stage_2"},
        {"$set": {
            "progress": 1.0,
            "status": "COMPLETED",
            "completedAt": datetime.utcnow()
        }}
    )
    time.sleep(6)
    
    # Step 9: Create validation
    print("Step 9: Creating auto-validation...")
    db["validations"].insert_one({
        "_id": f"{run_id}-auto-{int(time.time())}",
        "runId": run_id,
        "kind": "auto",
        "verdict": "pass",
        "rubric": {"overall": 0.85},
        "notes": "Test validation",
        "createdAt": datetime.utcnow(),
        "createdBy": "gpt-4o"
    })
    time.sleep(6)
    
    # Step 10: Set to AWAITING_HUMAN
    print("Step 10: Setting status to AWAITING_HUMAN...")
    runs.update_one(
        {"_id": run_id},
        {"$set": {
            "status": "AWAITING_HUMAN",
            "updatedAt": datetime.utcnow()
        }}
    )
    
    print("\n✅ Simulation complete!")
    print("   Frontend should now show: Status = AWAITING_HUMAN")
    print("   Polling should STOP (terminal state reached)\n")


def main():
    db = connect_mongodb()
    runs = db["runs"]
    
    # List existing runs
    existing_runs = list(runs.find(
        {"seed": {"$ne": True}},
        {"_id": 1, "status": 1, "hypothesisId": 1}
    ).limit(10))
    
    if not existing_runs:
        print("❌ No runs found in database")
        print("\nCreate a run first:")
        print("  1. Go to frontend /hypotheses page")
        print("  2. Create a hypothesis")
        print("  3. Run this script again\n")
        sys.exit(1)
    
    print("Available runs:\n")
    for i, run in enumerate(existing_runs, 1):
        print(f"{i}. {run['_id']} (status: {run['status']})")
    
    print(f"\nEnter number (1-{len(existing_runs)}) or run ID: ", end="")
    choice = input().strip()
    
    # Parse choice
    if choice.isdigit() and 1 <= int(choice) <= len(existing_runs):
        run_id = existing_runs[int(choice) - 1]["_id"]
    else:
        run_id = choice
    
    # Verify run exists
    run = runs.find_one({"_id": run_id})
    if not run:
        print(f"\n❌ Run {run_id} not found")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"Selected run: {run_id}")
    print(f"Current status: {run['status']}")
    print(f"{'='*60}\n")
    
    print("📱 Open this URL in your browser:")
    print(f"   http://localhost:3000/runs/{run_id}")
    print("\n🔍 Open browser console (F12) to see update logs")
    print("\nPress Enter when ready to start simulation...")
    input()
    
    simulate_run_progress(db, run_id)


if __name__ == "__main__":
    main()

