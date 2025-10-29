#!/usr/bin/env python3
"""
Delete a specific run and its associated data
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.environ.get("MONGODB_URL")
RUN_ID = "ad14830c-5b06-4753-9e30-9013b526d8b2"

if not MONGODB_URL:
    print("❌ MONGODB_URL not set")
    exit(1)

client = MongoClient(MONGODB_URL)
db = client['ai-scientist']

# Delete the run
result = db['runs'].delete_one({"_id": RUN_ID})
print(f"✓ Deleted run: {result.deleted_count} document(s)")

# Delete associated stages
stages_result = db['stages'].delete_many({"runId": RUN_ID})
print(f"✓ Deleted stages: {stages_result.deleted_count} document(s)")

# Delete associated events
events_result = db['events'].delete_many({"runId": RUN_ID})
print(f"✓ Deleted events: {events_result.deleted_count} document(s)")

# Delete associated artifacts
artifacts_result = db['artifacts'].delete_many({"runId": RUN_ID})
print(f"✓ Deleted artifacts: {artifacts_result.deleted_count} document(s)")

# Delete associated validations
validations_result = db['validations'].delete_many({"runId": RUN_ID})
print(f"✓ Deleted validations: {validations_result.deleted_count} document(s)")

# Delete associated paper analyses
analyses_result = db['paperAnalyses'].delete_many({"runId": RUN_ID})
print(f"✓ Deleted paper analyses: {analyses_result.deleted_count} document(s)")

print(f"\n✅ Run {RUN_ID} completely deleted from database!")

