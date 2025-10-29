#!/usr/bin/env python3
"""
Erase all data from MongoDB database.
Use with caution - this will delete ALL runs, hypotheses, events, etc.
"""
import os
from pymongo import MongoClient

MONGODB_URL = os.environ.get("MONGODB_URL", "")

if not MONGODB_URL:
    print("❌ MONGODB_URL not set in environment")
    exit(1)

# Safety confirmation
print("⚠️  WARNING: This will DELETE ALL DATA from the database!")
print("   Collections to be cleared:")
print("   - hypotheses")
print("   - runs")
print("   - stages")
print("   - events")
print("   - artifacts")
print("   - validations")
print()

response = input("Type 'DELETE ALL DATA' to confirm: ")

if response != "DELETE ALL DATA":
    print("❌ Cancelled - database not modified")
    exit(0)

print("\n🗑️  Erasing database...")

client = MongoClient(MONGODB_URL)
db = client['ai-scientist']

collections = [
    "hypotheses",
    "runs", 
    "stages",
    "events",
    "artifacts",
    "validations"
]

for collection_name in collections:
    collection = db[collection_name]
    count = collection.count_documents({})
    
    if count > 0:
        result = collection.delete_many({})
        print(f"✓ Deleted {result.deleted_count} documents from '{collection_name}'")
    else:
        print(f"  '{collection_name}' was already empty")

print("\n✨ Database erased successfully!")
print("   All collections are now empty.")

