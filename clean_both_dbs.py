#!/usr/bin/env python3
import os
import sys
from pymongo import MongoClient

MONGODB_URL = os.environ.get("MONGODB_URL", "")

if not MONGODB_URL:
    print("❌ MONGODB_URL environment variable not set")
    sys.exit(1)

COLLECTIONS = ["runs", "hypotheses", "stages", "validations", "artifacts", "events", "events_seen"]

client = MongoClient(MONGODB_URL)

print("\n" + "="*60)
print("Cleaning Both Databases")
print("="*60 + "\n")

for db_name in ["ai_scientist", "ai-scientist"]:
    print(f"Database: {db_name}")
    print("-"*60)
    
    db = client[db_name]
    total = 0
    
    for collection_name in COLLECTIONS:
        count = db[collection_name].count_documents({"seed": {"$ne": True}})
        if count > 0:
            result = db[collection_name].delete_many({"seed": {"$ne": True}})
            total += result.deleted_count
            print(f"  {collection_name:<20} deleted {result.deleted_count:>4} documents")
        else:
            print(f"  {collection_name:<20} (empty)")
    
    print(f"  {'SUBTOTAL':<20} deleted {total:>4} documents")
    print()

print("="*60)
print("✅ Both databases cleaned!")
print("="*60 + "\n")


