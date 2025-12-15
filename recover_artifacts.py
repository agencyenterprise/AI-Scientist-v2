#!/usr/bin/env python3
"""
Recovery script to list and re-register artifacts that exist in MinIO but not in MongoDB.
"""
import os
import sys
from datetime import datetime
from minio import Minio
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Configuration from environment
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "bucket-production-66d0.up.railway.app")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "ai-scientist")
MINIO_USE_SSL = os.getenv("MINIO_USE_SSL", "true").lower() == "true"

MONGODB_URI = os.getenv("MONGODB_URI")

def get_content_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".json": "application/json",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".py": "text/x-python",
        ".npy": "application/octet-stream",
        ".tar.gz": "application/gzip",
        ".gz": "application/gzip",
    }
    return types.get(ext, "application/octet-stream")

def get_artifact_kind(filename: str) -> str:
    if filename.endswith(".pdf"):
        return "paper"
    elif filename.endswith(".png") or filename.endswith(".jpg"):
        return "plot"
    elif filename.endswith(".tar.gz"):
        return "archive"
    elif filename.endswith(".npy"):
        return "data"
    else:
        return "other"

def list_minio_artifacts(run_id: str):
    """List all objects in MinIO for a given run."""
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_USE_SSL
    )
    
    prefix = f"runs/{run_id}/"
    objects = list(client.list_objects(MINIO_BUCKET, prefix=prefix, recursive=True))
    return objects

def list_db_artifacts(run_id: str):
    """List all artifacts in MongoDB for a given run."""
    client = MongoClient(MONGODB_URI)
    db = client.get_default_database()
    artifacts = list(db.artifacts.find({"runId": run_id}))
    return {a["key"] for a in artifacts}

def register_missing_artifacts(run_id: str, dry_run: bool = True):
    """Find and optionally register missing artifacts."""
    print(f"🔍 Checking run: {run_id}")
    print()
    
    # Get MinIO objects
    minio_objects = list_minio_artifacts(run_id)
    minio_keys = {obj.object_name for obj in minio_objects}
    print(f"📦 Found {len(minio_keys)} objects in MinIO")
    
    # Get DB artifacts
    db_keys = list_db_artifacts(run_id)
    print(f"📊 Found {len(db_keys)} artifacts in database")
    print()
    
    # Find missing
    missing_keys = minio_keys - db_keys
    
    if not missing_keys:
        print("✅ All MinIO objects are registered in database!")
        return
    
    print(f"⚠️  Found {len(missing_keys)} objects in MinIO NOT in database:")
    for key in sorted(missing_keys):
        print(f"   - {key}")
    print()
    
    if dry_run:
        print("🔸 DRY RUN - not registering. Run with --register to add to database.")
        return
    
    # Register missing artifacts
    print("📝 Registering missing artifacts...")
    client = MongoClient(MONGODB_URI)
    db = client.get_default_database()
    
    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_USE_SSL
    )
    
    import uuid
    for key in missing_keys:
        # Get object stats
        stat = minio_client.stat_object(MINIO_BUCKET, key)
        filename = os.path.basename(key)
        
        artifact = {
            "_id": str(uuid.uuid4()),
            "runId": run_id,
            "key": key,
            "uri": key,
            "contentType": get_content_type(filename),
            "size": stat.size,
            "kind": get_artifact_kind(filename),
            "sha256": None,  # We don't have this without downloading
            "createdAt": stat.last_modified or datetime.utcnow()
        }
        
        db.artifacts.insert_one(artifact)
        print(f"   ✅ Registered: {filename}")
    
    print()
    print(f"✅ Registered {len(missing_keys)} missing artifacts!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python recover_artifacts.py <run_id> [--register]")
        print()
        print("Options:")
        print("  --register    Actually register missing artifacts (default is dry-run)")
        sys.exit(1)
    
    run_id = sys.argv[1]
    dry_run = "--register" not in sys.argv
    
    register_missing_artifacts(run_id, dry_run=dry_run)

