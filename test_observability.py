#!/usr/bin/env python3
"""
Quick test to validate observability system is working.
Run this BEFORE deploying to pod to catch issues early.
"""
import os
import sys
import json
from pathlib import Path
from pymongo import MongoClient
from datetime import datetime
from ulid import ULID

print("="*60)
print("Observability System Test")
print("="*60)

errors = []

# Test 1: MongoDB Connection
print("\n1. Testing MongoDB connection...")
mongodb_url = os.environ.get('MONGODB_URL')
if not mongodb_url:
    errors.append("MONGODB_URL not set in environment")
    print("   ❌ MONGODB_URL not set")
else:
    try:
        client = MongoClient(mongodb_url)
        client.admin.command("ping")
        db = client['ai-scientist']
        print(f"   ✓ Connected to MongoDB")
        print(f"   ✓ Database: ai-scientist")
        
        # Check collections
        collections = db.list_collection_names()
        required = ['runs', 'hypotheses', 'events']
        for coll in required:
            if coll in collections:
                print(f"   ✓ Collection '{coll}' exists")
            else:
                errors.append(f"Collection '{coll}' missing")
                print(f"   ❌ Collection '{coll}' missing")
    except Exception as e:
        errors.append(f"MongoDB connection failed: {e}")
        print(f"   ❌ Connection failed: {e}")

# Test 2: OpenAI API Key
print("\n2. Testing OpenAI API key...")
openai_key = os.environ.get('OPENAI_API_KEY')
if not openai_key:
    errors.append("OPENAI_API_KEY not set")
    print("   ❌ OPENAI_API_KEY not set")
elif not openai_key.startswith('sk-'):
    errors.append("OPENAI_API_KEY appears invalid")
    print("   ❌ API key doesn't start with 'sk-'")
else:
    print(f"   ✓ OPENAI_API_KEY set ({openai_key[:15]}...)")

# Test 3: .env File
print("\n3. Checking .env file...")
if Path('.env').exists():
    print("   ✓ .env file exists")
    with open('.env') as f:
        content = f.read()
        if 'OPENAI_API_KEY' in content:
            print("   ✓ .env contains OPENAI_API_KEY")
        else:
            errors.append(".env missing OPENAI_API_KEY")
            print("   ❌ .env missing OPENAI_API_KEY")
        if 'MONGODB_URL' in content:
            print("   ✓ .env contains MONGODB_URL")
        else:
            errors.append(".env missing MONGODB_URL")
            print("   ❌ .env missing MONGODB_URL")
else:
    errors.append(".env file not found")
    print("   ❌ .env file not found in project root")

# Test 4: Required Files
print("\n4. Checking required files...")
required_files = [
    'pod_worker.py',
    'monitor_experiment.py',
    'ai_scientist/treesearch/perform_experiments_bfts_with_agentmanager.py'
]

for file_path in required_files:
    if Path(file_path).exists():
        print(f"   ✓ {file_path}")
    else:
        errors.append(f"Missing file: {file_path}")
        print(f"   ❌ {file_path} not found")

# Test 5: Create Test Event
print("\n5. Testing event creation...")
if mongodb_url:
    try:
        client = MongoClient(mongodb_url)
        db = client['ai-scientist']
        
        test_event = {
            "_id": str(ULID()),
            "runId": "test-run-id",
            "type": "ai.run.log",
            "data": {"message": "Test event", "level": "info"},
            "source": "test",
            "timestamp": datetime.utcnow()
        }
        
        db['events'].insert_one(test_event)
        print("   ✓ Created test event")
        
        # Clean up
        db['events'].delete_one({"_id": test_event["_id"]})
        print("   ✓ Cleaned up test event")
    except Exception as e:
        errors.append(f"Event creation failed: {e}")
        print(f"   ❌ Event creation failed: {e}")

# Summary
print("\n" + "="*60)
if errors:
    print(f"❌ FAILED - {len(errors)} error(s):")
    for err in errors:
        print(f"   - {err}")
    print("\nFix these issues before deploying!")
    sys.exit(1)
else:
    print("✅ ALL TESTS PASSED")
    print("\nYou're ready to deploy!")
    print("\nNext steps:")
    print("  1. On pod: git pull origin feat/additions")
    print("  2. On pod: python pod_worker.py")
    print("  3. Create a new hypothesis and watch the magic! 🎉")
    sys.exit(0)

