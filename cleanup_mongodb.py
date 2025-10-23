#!/usr/bin/env python3
"""
Clean MongoDB collections for fresh experiment starts.
Use with caution - this deletes data!
"""

import os
import sys
from pymongo import MongoClient
from datetime import datetime
import argparse

MONGODB_URL = os.environ.get("MONGODB_URL", "")

COLLECTIONS_TO_CLEAN = [
    "runs",
    "hypotheses",
    "stages",
    "validations",
    "artifacts",
    "events",
    "events_seen",
]

def connect_mongodb():
    """Connect to MongoDB"""
    if not MONGODB_URL:
        print("❌ MONGODB_URL environment variable not set", file=sys.stderr)
        print("Set it with: export MONGODB_URL='mongodb://...'")
        sys.exit(1)
    
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
            print(f"⚠️  No database name in URL, using default: {db_name}")
            print(f"   Set explicitly with: export MONGODB_DATABASE='your_db_name'\n")
        
        print(f"Using database: {db_name}\n")
        
        return client[db_name]
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}", file=sys.stderr)
        sys.exit(1)


def show_stats(db):
    """Show current database statistics"""
    print("="*60)
    print("Current Database Statistics")
    print("="*60 + "\n")
    
    total_docs = 0
    for collection_name in COLLECTIONS_TO_CLEAN:
        collection = db[collection_name]
        count = collection.count_documents({})
        total_docs += count
        print(f"{collection_name:<20} {count:>6} documents")
    
    print("-"*60)
    print(f"{'TOTAL':<20} {total_docs:>6} documents")
    print()


def cleanup_all(db, exclude_seed=True):
    """Clean all collections"""
    print("="*60)
    print("Cleaning All Collections")
    print("="*60 + "\n")
    
    filter_query = {"seed": {"$ne": True}} if exclude_seed else {}
    
    total_deleted = 0
    for collection_name in COLLECTIONS_TO_CLEAN:
        collection = db[collection_name]
        
        before_count = collection.count_documents(filter_query)
        
        if before_count > 0:
            result = collection.delete_many(filter_query)
            deleted = result.deleted_count
            total_deleted += deleted
            print(f"✓ {collection_name:<20} deleted {deleted:>6} documents")
        else:
            print(f"  {collection_name:<20} (empty, skipped)")
    
    print("-"*60)
    print(f"  {'TOTAL DELETED':<20} {total_deleted:>6} documents")
    print()


def cleanup_failed_runs(db):
    """Clean only failed/canceled runs and their related data"""
    print("="*60)
    print("Cleaning Failed & Canceled Runs")
    print("="*60 + "\n")
    
    runs_collection = db["runs"]
    
    # Find failed/canceled runs
    failed_runs = list(runs_collection.find(
        {"status": {"$in": ["FAILED", "CANCELED"]}, "seed": {"$ne": True}}
    ))
    
    if not failed_runs:
        print("No failed or canceled runs to clean.")
        return
    
    run_ids = [run["_id"] for run in failed_runs]
    
    print(f"Found {len(run_ids)} failed/canceled runs:\n")
    for run in failed_runs[:5]:  # Show first 5
        print(f"  - {run['_id']} (status: {run['status']})")
    if len(failed_runs) > 5:
        print(f"  ... and {len(failed_runs) - 5} more")
    print()
    
    # Delete related data
    total_deleted = 0
    
    # Runs
    result = runs_collection.delete_many({"_id": {"$in": run_ids}})
    print(f"✓ runs:         deleted {result.deleted_count} documents")
    total_deleted += result.deleted_count
    
    # Stages
    result = db["stages"].delete_many({"runId": {"$in": run_ids}})
    print(f"✓ stages:       deleted {result.deleted_count} documents")
    total_deleted += result.deleted_count
    
    # Validations
    result = db["validations"].delete_many({"runId": {"$in": run_ids}})
    print(f"✓ validations:  deleted {result.deleted_count} documents")
    total_deleted += result.deleted_count
    
    # Artifacts
    result = db["artifacts"].delete_many({"runId": {"$in": run_ids}})
    print(f"✓ artifacts:    deleted {result.deleted_count} documents")
    total_deleted += result.deleted_count
    
    # Events
    result = db["events"].delete_many({"runId": {"$in": run_ids}})
    print(f"✓ events:       deleted {result.deleted_count} documents")
    total_deleted += result.deleted_count
    
    print("-"*60)
    print(f"  TOTAL DELETED: {total_deleted} documents")
    print()


def cleanup_test_data(db):
    """Clean test data (events from test sources)"""
    print("="*60)
    print("Cleaning Test Data")
    print("="*60 + "\n")
    
    # Delete test events
    result = db["events"].delete_many({"source": {"$regex": "^test://"}})
    print(f"✓ Test events:       deleted {result.deleted_count} documents")
    
    # Delete test events_seen
    result = db["events_seen"].delete_many({"_id": {"$regex": "^test-"}})
    print(f"✓ Test events_seen:  deleted {result.deleted_count} documents")
    
    print()


def cleanup_old_events(db, days=7):
    """Clean old events (keep recent ones)"""
    print("="*60)
    print(f"Cleaning Events Older Than {days} Days")
    print("="*60 + "\n")
    
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Delete old events
    result = db["events"].delete_many({"timestamp": {"$lt": cutoff_date}})
    print(f"✓ Old events:        deleted {result.deleted_count} documents")
    
    # Delete old events_seen
    result = db["events_seen"].delete_many({"processedAt": {"$lt": cutoff_date}})
    print(f"✓ Old events_seen:   deleted {result.deleted_count} documents")
    
    print()


def cleanup_specific_run(db, run_id):
    """Clean a specific run and its related data"""
    print("="*60)
    print(f"Cleaning Run: {run_id}")
    print("="*60 + "\n")
    
    # Check if run exists
    run = db["runs"].find_one({"_id": run_id})
    if not run:
        print(f"❌ Run {run_id} not found")
        return
    
    print(f"Run status: {run['status']}")
    print(f"Hypothesis: {run['hypothesisId']}\n")
    
    total_deleted = 0
    
    # Delete run
    result = db["runs"].delete_one({"_id": run_id})
    print(f"✓ Run:          deleted {result.deleted_count} document")
    total_deleted += result.deleted_count
    
    # Delete stages
    result = db["stages"].delete_many({"runId": run_id})
    print(f"✓ Stages:       deleted {result.deleted_count} documents")
    total_deleted += result.deleted_count
    
    # Delete validations
    result = db["validations"].delete_many({"runId": run_id})
    print(f"✓ Validations:  deleted {result.deleted_count} documents")
    total_deleted += result.deleted_count
    
    # Delete artifacts
    result = db["artifacts"].delete_many({"runId": run_id})
    print(f"✓ Artifacts:    deleted {result.deleted_count} documents")
    total_deleted += result.deleted_count
    
    # Delete events
    result = db["events"].delete_many({"runId": run_id})
    print(f"✓ Events:       deleted {result.deleted_count} documents")
    total_deleted += result.deleted_count
    
    print("-"*60)
    print(f"  TOTAL DELETED: {total_deleted} documents")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Clean MongoDB collections for AI Scientist",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show current stats (no cleaning)
  python cleanup_mongodb.py --stats
  
  # Clean all non-seed data (fresh start)
  python cleanup_mongodb.py --all
  
  # Clean including seed data (DANGEROUS!)
  python cleanup_mongodb.py --all --include-seed
  
  # Clean only failed runs
  python cleanup_mongodb.py --failed
  
  # Clean test data
  python cleanup_mongodb.py --test
  
  # Clean specific run
  python cleanup_mongodb.py --run <run_id>
  
  # Clean old events (>7 days)
  python cleanup_mongodb.py --old-events --days 7
        """
    )
    
    parser.add_argument("--stats", action="store_true", help="Show database statistics only")
    parser.add_argument("--all", action="store_true", help="Clean all collections")
    parser.add_argument("--failed", action="store_true", help="Clean failed/canceled runs only")
    parser.add_argument("--test", action="store_true", help="Clean test data only")
    parser.add_argument("--run", type=str, help="Clean specific run ID")
    parser.add_argument("--old-events", action="store_true", help="Clean old events")
    parser.add_argument("--days", type=int, default=7, help="Days threshold for old events (default: 7)")
    parser.add_argument("--include-seed", action="store_true", help="Include seed data (use with --all)")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    if not any([args.stats, args.all, args.failed, args.test, args.run, args.old_events]):
        parser.print_help()
        return
    
    db = connect_mongodb()
    
    # Show stats first
    show_stats(db)
    
    if args.stats:
        return
    
    # Confirm destructive operations
    if not args.yes:
        print("⚠️  WARNING: This will delete data from MongoDB!")
        print()
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            return
        print()
    
    # Perform cleanup
    if args.all:
        cleanup_all(db, exclude_seed=not args.include_seed)
    elif args.failed:
        cleanup_failed_runs(db)
    elif args.test:
        cleanup_test_data(db)
    elif args.run:
        cleanup_specific_run(db, args.run)
    elif args.old_events:
        cleanup_old_events(db, days=args.days)
    
    # Show stats after
    print()
    show_stats(db)
    
    print("="*60)
    print("✅ Cleanup Complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()

