#!/usr/bin/env python3
"""
Script to hide specific runs from the dashboard by setting hidden: true
"""

import os
import sys
from pymongo import MongoClient
from datetime import datetime, timezone

MONGODB_URL = os.environ.get("MONGODB_URL", "")

RUN_IDS_TO_HIDE = [
    "f7f195a5-a395-434f-a371-b8772b5683c3",  # Observability Test
    "cbaf7ba6-44fe-413f-a244-640f224ab9fc",  # Integration Test
    "349fca1e-1e8c-4992-8fc3-f38c644c0aee",  # Crystal LLMs (failed stage 4)
    "1c7e3b0e-1811-4451-a424-ad68b7d3e591",  # Crystal LLMs (failed stage 1)
]


def connect_mongo():
    if not MONGODB_URL:
        print("❌ MONGODB_URL environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    client = MongoClient(MONGODB_URL)
    try:
        client.admin.command("ping")
        
        db_name = os.environ.get("MONGODB_DATABASE")
        
        if not db_name:
            if "/" in MONGODB_URL:
                parts = [p for p in MONGODB_URL.split("/") if p]
                if parts:
                    extracted = parts[-1].split("?")[0]
                    if extracted and not extracted.startswith("mongodb"):
                        db_name = extracted
        
        if not db_name:
            db_name = "ai-scientist"
        
        print(f"✓ Connected to MongoDB")
        print(f"  Database: {db_name}\n")
        
        return client[db_name]
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}", file=sys.stderr)
        sys.exit(1)


def hide_runs(db):
    """Hide specific runs by setting hidden: true"""
    runs_collection = db["runs"]
    
    print("="*60)
    print("Hiding Runs from Dashboard")
    print("="*60 + "\n")
    
    for run_id in RUN_IDS_TO_HIDE:
        run = runs_collection.find_one({"_id": run_id})
        
        if not run:
            print(f"⚠  Run not found: {run_id}")
            continue
        
        status = run.get("status", "UNKNOWN")
        hypothesis_id = run.get("hypothesisId", "unknown")
        
        result = runs_collection.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "hidden": True,
                    "updatedAt": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"✅ Hidden run: {run_id}")
            print(f"   Status: {status}, Hypothesis: {hypothesis_id}")
        else:
            print(f"⚠  Already hidden: {run_id}")
    
    print()
    print("="*60)
    print("✅ Complete!")
    print("="*60 + "\n")


def show_hidden_runs(db):
    """Show all hidden runs"""
    runs_collection = db["runs"]
    
    hidden_runs = list(runs_collection.find({"hidden": True}).sort("createdAt", -1))
    
    if not hidden_runs:
        print("No hidden runs found.")
        return
    
    print(f"\n{'='*60}")
    print(f"Hidden Runs ({len(hidden_runs)} total)")
    print(f"{'='*60}\n")
    
    for run in hidden_runs:
        run_id = run["_id"]
        status = run.get("status", "UNKNOWN")
        hypothesis_id = run.get("hypothesisId", "unknown")[:36]
        created = run["createdAt"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(run["createdAt"], datetime) else str(run["createdAt"])
        
        print(f"ID:         {run_id}")
        print(f"Status:     {status}")
        print(f"Hypothesis: {hypothesis_id}")
        print(f"Created:    {created}")
        print()


def unhide_run(db, run_id):
    """Unhide a specific run"""
    runs_collection = db["runs"]
    
    result = runs_collection.update_one(
        {"_id": run_id},
        {
            "$set": {
                "hidden": False,
                "updatedAt": datetime.now(timezone.utc)
            }
        }
    )
    
    if result.matched_count == 0:
        print(f"❌ Run not found: {run_id}")
    elif result.modified_count > 0:
        print(f"✅ Unhidden run: {run_id}")
    else:
        print(f"⚠  Run was already visible: {run_id}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Hide/unhide runs from the dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Hide the predefined runs
  python hide_runs.py --hide
  
  # Show all hidden runs
  python hide_runs.py --list
  
  # Unhide a specific run
  python hide_runs.py --unhide <run_id>
        """
    )
    
    parser.add_argument("--hide", action="store_true", help="Hide the predefined runs")
    parser.add_argument("--list", action="store_true", help="List all hidden runs")
    parser.add_argument("--unhide", type=str, help="Unhide a specific run")
    
    args = parser.parse_args()
    
    if not any([args.hide, args.list, args.unhide]):
        parser.print_help()
        return
    
    db = connect_mongo()
    
    if args.hide:
        hide_runs(db)
    elif args.list:
        show_hidden_runs(db)
    elif args.unhide:
        unhide_run(db, args.unhide)


if __name__ == "__main__":
    main()

