#!/usr/bin/env python
"""Clear recently created ChatGPT-sourced runs and hypotheses"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

client = MongoClient(os.getenv("MONGODB_URL"))
db = client["ai-scientist"]

runs_collection = db["runs"]
hypotheses_collection = db["hypotheses"]

# Find runs created by chatgpt_processor in the last 2 hours
recent = datetime.utcnow() - timedelta(hours=2)

result = hypotheses_collection.delete_many({
    "createdBy": "chatgpt_processor",
    "createdAt": {"$gte": recent}
})
print(f"✓ Deleted {result.deleted_count} hypotheses")

result = runs_collection.delete_many({
    "createdAt": {"$gte": recent}
})
print(f"✓ Deleted {result.deleted_count} runs")

print("\nCleared! Now fix the format and re-enqueue.")





