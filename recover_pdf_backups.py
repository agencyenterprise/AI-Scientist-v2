#!/usr/bin/env python3
"""
Recover PDF backups from local_pdf_backups/ directory and upload them to MinIO + MongoDB.

Usage:
    python recover_pdf_backups.py                    # List all backups
    python recover_pdf_backups.py <run_id>           # Upload PDFs for specific run
    python recover_pdf_backups.py --all              # Upload all missing PDFs
    
Example:
    python recover_pdf_backups.py 1b16c163-f33b-41bf-b5e2-60615e3b8608
"""

import os
import sys
import base64
import hashlib
import requests
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "https://ai-scientist-v2-production.up.railway.app")
MONGODB_URL = os.getenv("MONGODB_URL")
BACKUP_DIR = Path("local_pdf_backups")


def get_content_type(filename: str) -> str:
    if filename.endswith(".pdf"):
        return "application/pdf"
    return "application/octet-stream"


def upload_artifact(run_id: str, file_path: str, kind: str) -> bool:
    """Upload artifact to MinIO via presigned URL."""
    filename = os.path.basename(file_path)
    content_type = get_content_type(filename)
    
    try:
        print(f"   📤 Requesting presigned URL...")
        resp = requests.post(
            f"{CONTROL_PLANE_URL}/api/runs/{run_id}/artifacts/presign",
            json={"action": "put", "filename": filename, "content_type": content_type},
            timeout=30
        )
        resp.raise_for_status()
        presigned_url = resp.json()["url"]
        
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        
        print(f"   📤 Uploading {len(file_bytes)} bytes to MinIO...")
        resp = requests.put(presigned_url, data=file_bytes, timeout=300)
        resp.raise_for_status()
        
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        
        # Register in MongoDB
        from pymongo import MongoClient
        from uuid import uuid4
        
        client = MongoClient(MONGODB_URL)
        db = client['ai-scientist']
        
        artifact_doc = {
            "_id": str(uuid4()),
            "runId": run_id,
            "key": f"runs/{run_id}/{filename}",
            "uri": f"runs/{run_id}/{filename}",  # Required field!
            "size": len(file_bytes),
            "sha256": sha256,
            "contentType": content_type,
            "kind": kind,
            "createdAt": datetime.now(timezone.utc)
        }
        
        db.artifacts.insert_one(artifact_doc)
        print(f"   ✅ Artifact uploaded and registered: {filename}")
        return True
        
    except Exception as e:
        print(f"   ❌ Upload failed: {e}")
        return False


def save_pdf_to_mongodb(run_id: str, file_path: str, kind: str, is_final: bool) -> bool:
    """Save PDF as base64 in MongoDB for redundancy."""
    try:
        from pymongo import MongoClient
        
        client = MongoClient(MONGODB_URL)
        db = client['ai-scientist']
        
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        paper_backup = {
            "runId": run_id,
            "filename": filename,
            "kind": kind,
            "is_final": is_final,
            "size_bytes": len(pdf_bytes),
            "pdf_base64": pdf_base64,
            "createdAt": datetime.now(timezone.utc)
        }
        
        db['paper_backups'].update_one(
            {"runId": run_id, "filename": filename},
            {"$set": paper_backup},
            upsert=True
        )
        
        print(f"   ✅ Saved to MongoDB: {filename} ({len(pdf_bytes)} bytes)")
        return True
        
    except Exception as e:
        print(f"   ❌ MongoDB save failed: {e}")
        return False


def list_backups():
    """List all PDF backups grouped by run ID."""
    if not BACKUP_DIR.exists():
        print(f"No backup directory found at {BACKUP_DIR}")
        return {}
    
    backups = {}
    for pdf_file in BACKUP_DIR.glob("*.pdf"):
        # Extract run_id from filename (format: {run_id}_{hash}_{type}.pdf)
        parts = pdf_file.name.split('_')
        if len(parts) >= 2:
            # Run ID is a UUID, first 5 parts joined by dashes
            run_id = '-'.join(parts[0].split('-')[:5])
            if len(run_id) == 36:  # Valid UUID length
                if run_id not in backups:
                    backups[run_id] = []
                backups[run_id].append(pdf_file)
    
    return backups


def check_artifacts_exist(run_id: str) -> dict:
    """Check what artifacts already exist for a run."""
    from pymongo import MongoClient
    
    client = MongoClient(MONGODB_URL)
    db = client['ai-scientist']
    
    existing = {
        "paper_artifacts": list(db.artifacts.find({"runId": run_id, "kind": "paper"})),
        "paper_backups": list(db.paper_backups.find({"runId": run_id}))
    }
    
    return existing


def recover_run(run_id: str):
    """Recover PDFs for a specific run."""
    print(f"\n{'='*60}")
    print(f"🔧 Recovering PDFs for run: {run_id}")
    print(f"{'='*60}")
    
    backups = list_backups()
    
    if run_id not in backups:
        print(f"❌ No backups found for run {run_id}")
        return
    
    pdf_files = backups[run_id]
    print(f"Found {len(pdf_files)} PDF backups")
    
    existing = check_artifacts_exist(run_id)
    print(f"Existing artifacts: {len(existing['paper_artifacts'])}")
    print(f"Existing MongoDB backups: {len(existing['paper_backups'])}")
    
    for pdf_path in pdf_files:
        filename = pdf_path.name
        print(f"\n📄 Processing: {filename}")
        
        # Determine kind and is_final
        is_final = "final" in filename.lower()
        kind = "paper" if is_final or "reflection" not in filename.lower() else "reflection"
        
        # Check if already exists
        existing_artifact = next(
            (a for a in existing['paper_artifacts'] if filename in a.get('key', '')),
            None
        )
        
        if existing_artifact:
            print(f"   ⏭️ Artifact already exists in MinIO, skipping upload")
        else:
            upload_artifact(run_id, str(pdf_path), kind)
        
        # Always ensure MongoDB backup exists
        existing_backup = next(
            (b for b in existing['paper_backups'] if b.get('filename') == filename),
            None
        )
        
        if existing_backup:
            print(f"   ⏭️ MongoDB backup already exists")
        else:
            save_pdf_to_mongodb(run_id, str(pdf_path), kind, is_final)
    
    print(f"\n✅ Recovery complete for {run_id}")


def main():
    if len(sys.argv) < 2:
        # List all backups
        print("=" * 60)
        print("📋 PDF Backups in local_pdf_backups/")
        print("=" * 60)
        
        backups = list_backups()
        
        if not backups:
            print("No backups found")
            return
        
        for run_id, files in sorted(backups.items()):
            print(f"\n🔹 Run: {run_id}")
            existing = check_artifacts_exist(run_id)
            print(f"   MinIO artifacts: {len(existing['paper_artifacts'])}")
            print(f"   MongoDB backups: {len(existing['paper_backups'])}")
            for f in files:
                size_kb = f.stat().st_size / 1024
                print(f"   - {f.name} ({size_kb:.1f} KB)")
        
        print(f"\n💡 To recover a specific run: python {sys.argv[0]} <run_id>")
        print(f"💡 To recover all runs: python {sys.argv[0]} --all")
        
    elif sys.argv[1] == "--all":
        backups = list_backups()
        for run_id in backups:
            recover_run(run_id)
    else:
        recover_run(sys.argv[1])


if __name__ == "__main__":
    main()

