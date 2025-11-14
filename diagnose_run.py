#!/usr/bin/env python3
"""
Diagnostic script to investigate a failed run and check the state of summary files.
"""

import json
import os
import sys
from pathlib import Path
from pymongo import MongoClient
from dotenv import load_dotenv

def check_summary_files(experiment_dir):
    """Check the state of summary files in an experiment directory."""
    print(f"\n{'='*60}")
    print(f"Checking experiment directory: {experiment_dir}")
    print(f"{'='*60}\n")
    
    summary_files = [
        "logs/0-run/baseline_summary.json",
        "logs/0-run/research_summary.json",
        "logs/0-run/ablation_summary.json",
    ]
    
    for fname in summary_files:
        path = os.path.join(experiment_dir, fname)
        print(f"File: {fname}")
        
        if os.path.exists(path):
            print(f"  ✓ Exists")
            
            # Check file size
            size = os.path.getsize(path)
            print(f"  Size: {size} bytes")
            
            # Try to read and parse
            try:
                with open(path, 'r') as f:
                    content = f.read()
                    if not content.strip():
                        print(f"  ⚠ File is empty")
                    else:
                        data = json.loads(content)
                        if data is None:
                            print(f"  ⚠ File contains null")
                        elif isinstance(data, dict):
                            print(f"  ✓ Valid dict with {len(data)} keys: {list(data.keys())}")
                        elif isinstance(data, list):
                            print(f"  ✓ Valid list with {len(data)} items")
                        else:
                            print(f"  ⚠ Unexpected type: {type(data)}")
            except json.JSONDecodeError as e:
                print(f"  ✗ Invalid JSON: {e}")
            except Exception as e:
                print(f"  ✗ Error reading file: {e}")
        else:
            print(f"  ✗ Does not exist")
        
        print()

def check_mongodb_run(run_id):
    """Check the run status in MongoDB."""
    load_dotenv()
    mongo_uri = os.getenv('MONGODB_URL')
    
    if not mongo_uri:
        print("⚠ MONGODB_URL not found in environment")
        return None
    
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        db = client['ai-scientist']
        
        # Try finding by _id (MongoDB's default) or hypothesisId
        run = db.runs.find_one({'_id': run_id})
        if not run:
            run = db.runs.find_one({'hypothesisId': run_id})
        
        if run:
            print(f"\n{'='*60}")
            print(f"MongoDB Run Status")
            print(f"{'='*60}\n")
            print(f"Run ID: {run.get('_id', run_id)}")
            print(f"Hypothesis ID: {run.get('hypothesisId', 'N/A')}")
            print(f"Status: {run.get('status')}")
            print(f"Current Stage: {run.get('currentStage', {}).get('name', 'N/A')}")
            print(f"Stage Progress: {run.get('currentStage', {}).get('progress', 'N/A')}")
            print(f"Pod: {run.get('pod', {}).get('id', 'N/A')}")
            print(f"Created At: {run.get('createdAt')}")
            print(f"Started At: {run.get('startedAt')}")
            print(f"Failed At: {run.get('failedAt', 'N/A')}")
            
            if run.get('errorMessage') or run.get('errorType'):
                print(f"\nError Details:")
                print(f"  Type: {run.get('errorType', 'N/A')}")
                print(f"  Message: {run.get('errorMessage', 'N/A')}")
                if run.get('errorTraceback'):
                    print(f"  Traceback:\n{run.get('errorTraceback')[:800]}...")
            
            # Try to get workspace directory from events or stages
            workspace = None
            if 'stages' in db.list_collection_names():
                stage = db.stages.find_one({'runId': run.get('_id')})
                if stage:
                    workspace = stage.get('workspace_dir')
            
            if workspace:
                print(f"\nWorkspace: {workspace}")
                run['workspace_dir'] = workspace
            
            return run
        else:
            print(f"\n⚠ Run {run_id} not found in MongoDB")
            return None
            
    except Exception as e:
        print(f"\n⚠ Error connecting to MongoDB: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python diagnose_run.py <run_id> [experiment_dir]")
        print("\nExamples:")
        print("  python diagnose_run.py 4ea43a49-8747-42f8-9edb-10e6c0f6c7d6")
        print("  python diagnose_run.py 4ea43a49-8747-42f8-9edb-10e6c0f6c7d6 /workspace/experiments/...")
        sys.exit(1)
    
    run_id = sys.argv[1]
    
    # Check MongoDB
    run = check_mongodb_run(run_id)
    
    # Get experiment directory
    if len(sys.argv) >= 3:
        experiment_dir = sys.argv[2]
    elif run and run.get('workspace_dir'):
        experiment_dir = run['workspace_dir']
    else:
        print("\n⚠ Could not determine experiment directory")
        print("Please provide it as a second argument")
        sys.exit(1)
    
    # Check summary files
    if os.path.exists(experiment_dir):
        check_summary_files(experiment_dir)
    else:
        print(f"\n⚠ Experiment directory not found: {experiment_dir}")

if __name__ == "__main__":
    main()

