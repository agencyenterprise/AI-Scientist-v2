#!/usr/bin/env python3
"""
Mark run 78762df7-c4b8-4def-90fa-2206bb2564eb as COMPLETED
since the PDF was actually generated successfully.
"""
import os
from pymongo import MongoClient
from datetime import datetime

MONGODB_URL = os.environ.get("MONGODB_URL", "")
RUN_ID = "78762df7-c4b8-4def-90fa-2206bb2564eb"

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

print(f"Current status: {run.get('status')}")
print(f"Current error: {run.get('errorMessage', 'None')}")
print(f"\nStages:")
stages = list(db['stages'].find({'runId': RUN_ID}))
for stage in stages:
    print(f"  {stage['name']}: {stage.get('status', 'UNKNOWN')} (progress: {stage.get('progress', 0)})")

print(f"\n{'='*60}")
print(f"Updating run to COMPLETED...")
print(f"{'='*60}\n")

# Update run to COMPLETED
result = db['runs'].update_one(
    {'_id': RUN_ID},
    {'$set': {
        'status': 'COMPLETED',
        'completedAt': datetime.utcnow(),
        'updatedAt': datetime.utcnow()
    },
    '$unset': {
        'errorMessage': '',
        'errorType': '',
        'failedAt': ''
    }}
)

# Mark Stage_1 as COMPLETED if it's still RUNNING
stage1 = db['stages'].find_one({'runId': RUN_ID, 'name': 'Stage_1'})
if stage1 and stage1.get('status') == 'RUNNING':
    print("Fixing Stage_1 status (RUNNING -> COMPLETED)...")
    db['stages'].update_one(
        {'runId': RUN_ID, 'name': 'Stage_1'},
        {'$set': {
            'status': 'COMPLETED',
            'progress': 1.0,
            'completedAt': datetime.utcnow()
        }}
    )

print(f"✅ Run updated: {result.modified_count} document(s) modified")

# Verify
run = db['runs'].find_one({'_id': RUN_ID})
print(f"\nNew status: {run.get('status')}")
print(f"Completed at: {run.get('completedAt')}")

print(f"\nFinal stages:")
stages = list(db['stages'].find({'runId': RUN_ID}))
for stage in stages:
    print(f"  {stage['name']}: {stage.get('status', 'UNKNOWN')} (progress: {stage.get('progress', 0)})")

print(f"\n✅ Run {RUN_ID} marked as COMPLETED")

