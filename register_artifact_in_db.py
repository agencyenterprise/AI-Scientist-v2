#!/usr/bin/env python3
"""
Register an already-uploaded artifact in MongoDB.
Use this after manually uploading to MinIO.

Usage:
    python register_artifact_in_db.py <run_id> <minio_key> [minio_endpoint]
    
Example:
    python register_artifact_in_db.py 4ea43a49-8747-42f8-9edb-10e6c0f6c7d6 \
        runs/4ea43a49-8747-42f8-9edb-10e6c0f6c7d6/tmp63zoshcf.tar.gz
"""

import os
import sys
from pymongo import MongoClient
from uuid import uuid4
from datetime import datetime
from pathlib import Path


def load_env():
    """Load environment variables from .env"""
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    run_id = sys.argv[1]
    minio_key = sys.argv[2]
    minio_endpoint = sys.argv[3] if len(sys.argv) > 3 else os.getenv('MINIO_ENDPOINT', 'minio.example.com')
    
    # Load environment
    load_env()
    
    print(f"{'='*70}")
    print(f"📝 Register Artifact in Database")
    print(f"{'='*70}")
    print(f"Run ID: {run_id}")
    print(f"MinIO Key: {minio_key}")
    print(f"MinIO Endpoint: {minio_endpoint}")
    
    # Connect to MongoDB
    mongodb_url = os.getenv('MONGODB_URL')
    if not mongodb_url:
        print("❌ MONGODB_URL not found in environment")
        sys.exit(1)
    
    try:
        mongo_client = MongoClient(mongodb_url, serverSelectionTimeoutMS=5000)
        db = mongo_client['ai-scientist']
        
        # Create artifact document
        artifact_doc = {
            "_id": str(uuid4()),
            "runId": run_id,
            "key": minio_key,
            "uri": f"https://{minio_endpoint}/ai-scientist/{minio_key}",
            "contentType": "application/gzip",
            "kind": "archive",
            "createdAt": datetime.utcnow()
        }
        
        print(f"\n📝 Registering artifact...")
        result = db.artifacts.insert_one(artifact_doc)
        
        print(f"✅ Artifact registered successfully!")
        print(f"   Artifact ID: {artifact_doc['_id']}")
        print(f"\n{'='*70}")
        
    except Exception as e:
        print(f"❌ Failed to register artifact: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

