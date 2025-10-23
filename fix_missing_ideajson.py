#!/usr/bin/env python3
"""
Fix hypotheses in MongoDB that are missing ideaJson field.
This will update all hypotheses without ideaJson to have a basic structure.
"""

import os
from pymongo import MongoClient

MONGODB_URL = os.environ.get("MONGODB_URL", "")

if not MONGODB_URL:
    print("❌ MONGODB_URL not set in environment")
    exit(1)

client = MongoClient(MONGODB_URL)
db = client['ai-scientist']
hypotheses_collection = db['hypotheses']

missing_ideajson = list(hypotheses_collection.find({"ideaJson": {"$exists": False}}))

if not missing_ideajson:
    print("✅ All hypotheses have ideaJson!")
    exit(0)

print(f"Found {len(missing_ideajson)} hypotheses missing ideaJson:\n")

for hyp in missing_ideajson:
    print(f"  - {hyp.get('title', 'Untitled')} ({hyp['_id']})")
    
    title = hyp.get('title', 'Untitled')
    idea = hyp.get('idea', '')
    
    idea_json = {
        "Name": title.lower().replace(' ', '_').replace('-', '_'),
        "Title": title,
        "Short Hypothesis": idea[:200] if idea else title,
        "Abstract": idea if idea else title,
        "Experiments": [
            "Implement the proposed approach",
            "Test on relevant datasets",
            "Evaluate performance metrics"
        ],
        "Risk Factors and Limitations": [
            "Computational complexity",
            "Generalization to other domains"
        ]
    }
    
    result = hypotheses_collection.update_one(
        {"_id": hyp['_id']},
        {"$set": {"ideaJson": idea_json}}
    )
    
    if result.modified_count > 0:
        print(f"    ✓ Updated")
    else:
        print(f"    ⚠️  Failed to update")

print(f"\n✨ Done! Updated {len(missing_ideajson)} hypotheses")


