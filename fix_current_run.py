#!/usr/bin/env python3
"""
Fix the status of the currently running experiment.
Changes status from FAILED to RUNNING since it's actually still executing.
"""
import os
from pymongo import MongoClient
from datetime import datetime

MONGODB_URL = os.environ.get("MONGODB_URL", "")
RUN_ID = "ea8242d9-de15-4a1b-a144-68b46953123e"

if not MONGODB_URL:
    print("❌ MONGODB_URL environment variable not set")
    exit(1)

client = MongoClient(MONGODB_URL)
db = client['ai-scientist']

# Check current status
run = db['runs'].find_one({'_id': RUN_ID})
if not run:
    print(f"❌ Run {RUN_ID} not found")
    exit(1)

print(f"{'='*60}")
print(f"Current Run Status")
print(f"{'='*60}")
print(f"Run ID: {RUN_ID}")
print(f"Status: {run.get('status')}")
print(f"Started: {run.get('startedAt')}")
print(f"Failed At: {run.get('failedAt', 'N/A')}")
print(f"Error Type: {run.get('errorType', 'None')}")
print(f"Error Message: {run.get('errorMessage', 'None')}")
print(f"Current Stage: {run.get('currentStage', {}).get('name', 'Unknown')}")
print()

# Check stages
stages = list(db['stages'].find({'runId': RUN_ID}))
print(f"Stages:")
for stage in stages:
    print(f"  {stage['name']}: {stage.get('status', 'UNKNOWN')} (progress: {stage.get('progress', 0):.1%})")
print()

print(f"{'='*60}")
print(f"Fixing Status...")
print(f"{'='*60}\n")

# Update run to RUNNING
result = db['runs'].update_one(
    {'_id': RUN_ID},
    {
        '$set': {
            'status': 'RUNNING',
            'updatedAt': datetime.utcnow()
        },
        '$unset': {
            'errorMessage': '',
            'errorType': '',
            'failedAt': ''
        }
    }
)

print(f"✅ Run status updated: {result.modified_count} document(s) modified")

# Mark Stage_1 as RUNNING if it's showing as something else
stage1 = db['stages'].find_one({'runId': RUN_ID, 'name': 'Stage_1'})
if stage1:
    current_stage_status = stage1.get('status')
    print(f"   Stage_1 status: {current_stage_status}")
    
    if current_stage_status != 'RUNNING':
        print(f"   Fixing Stage_1 status ({current_stage_status} -> RUNNING)...")
        db['stages'].update_one(
            {'runId': RUN_ID, 'name': 'Stage_1'},
            {'$set': {
                'status': 'RUNNING',
                'updatedAt': datetime.utcnow()
            }}
        )
        print(f"   ✅ Stage_1 status updated")
else:
    print(f"   ⚠️ Stage_1 not found in database")

print()

# Verify
run = db['runs'].find_one({'_id': RUN_ID})
print(f"{'='*60}")
print(f"Updated Status")
print(f"{'='*60}")
print(f"Status: {run.get('status')}")
print(f"Error Message: {run.get('errorMessage', 'None')}")
print(f"Error Type: {run.get('errorType', 'None')}")
print()

print(f"Final stages:")
stages = list(db['stages'].find({'runId': RUN_ID}))
for stage in stages:
    print(f"  {stage['name']}: {stage.get('status', 'UNKNOWN')} (progress: {stage.get('progress', 0):.1%})")

print()
print(f"✅ Run {RUN_ID} is now marked as RUNNING")
print(f"   The dashboard should reflect this change shortly.")

