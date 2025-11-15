#!/usr/bin/env python3
"""
Manual script to upload experiment archive from pod to MinIO.
Run this on the pod when an experiment directory needs to be manually archived.

Usage:
    python manual_upload_experiment_archive.py <run_id> [experiment_dir] [control_plane_url]
    
Example:
    python manual_upload_experiment_archive.py 4ea43a49-8747-42f8-9edb-10e6c0f6c7d6
    
    # Or specify explicit directory:
    python manual_upload_experiment_archive.py 4ea43a49-8747-42f8-9edb-10e6c0f6c7d6 \
        /workspace/AI-Scientist-v2/experiments/2025-11-14_08-37-14_operator_first_coinduction_protocol_run_4ea43a49-8747-42f8-9edb-10e6c0f6c7d6
    
    # Or specify control plane URL:
    python manual_upload_experiment_archive.py 4ea43a49-8747-42f8-9edb-10e6c0f6c7d6 \
        /path/to/experiment/dir \
        https://ai-scientist-v2-production.up.railway.app
"""

import os
import sys
import tarfile
import tempfile
import hashlib
import requests
from pathlib import Path
from datetime import datetime


def get_experiment_dir(run_id, explicit_dir=None):
    """Find the experiment directory for a given run_id."""
    if explicit_dir:
        if os.path.exists(explicit_dir):
            return explicit_dir
        else:
            print(f"❌ Specified directory does not exist: {explicit_dir}")
            return None
    
    # Search in experiments folder
    exp_base = Path("/workspace/AI-Scientist-v2/experiments")
    if not exp_base.exists():
        print(f"❌ Experiments directory not found: {exp_base}")
        return None
    
    # Look for directory containing the run_id
    for exp_dir in exp_base.iterdir():
        if exp_dir.is_dir() and run_id in exp_dir.name:
            return str(exp_dir)
    
    print(f"❌ Could not find experiment directory for run {run_id}")
    print(f"   Searched in: {exp_base}")
    return None


def create_archive(experiment_dir):
    """Create a .tar.gz archive of the experiment directory."""
    print(f"\n📦 Creating archive...")
    
    with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
        archive_path = tmp.name
    
    try:
        with tarfile.open(archive_path, 'w:gz') as tar:
            print(f"   Adding experiment directory: {experiment_dir}")
            tar.add(experiment_dir, arcname=os.path.basename(experiment_dir))
            
            # Also add ideas if they exist
            ideas_path = Path("/workspace/AI-Scientist-v2/ai_scientist/ideas")
            if ideas_path.exists():
                print(f"   Adding ideas directory")
                tar.add(str(ideas_path), arcname='ideas')
        
        file_size = os.path.getsize(archive_path)
        print(f"✓ Archive created: {archive_path}")
        print(f"  Size: {file_size / (1024*1024):.2f} MB")
        
        return archive_path
    except Exception as e:
        os.unlink(archive_path)
        raise e


def upload_archive_to_minio(run_id, archive_path, control_plane_url):
    """Upload archive to MinIO via presigned URL."""
    print(f"\n📤 Uploading to MinIO...")
    
    filename = os.path.basename(archive_path)
    
    try:
        # Step 1: Get presigned upload URL
        print(f"   Requesting presigned URL from control plane...")
        resp = requests.post(
            f"{control_plane_url}/api/runs/{run_id}/artifacts/presign",
            json={"action": "put", "filename": filename, "content_type": "application/gzip"},
            timeout=30
        )
        resp.raise_for_status()
        presigned_url = resp.json()["url"]
        print(f"   ✓ Got presigned URL")
        
        # Step 2: Upload file to MinIO
        print(f"   Uploading {filename}...")
        with open(archive_path, 'rb') as f:
            file_bytes = f.read()
        
        resp = requests.put(presigned_url, data=file_bytes, timeout=300)
        resp.raise_for_status()
        print(f"   ✓ Upload complete ({len(file_bytes) / (1024*1024):.2f} MB)")
        
        # Step 3: Calculate SHA256
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        
        # Step 4: Register artifact in database
        print(f"   Registering artifact in database...")
        resp = requests.post(
            f"{control_plane_url}/api/ingest/event",
            json={
                "specversion": "1.0",
                "id": f"artifact-{run_id}-{filename}",
                "source": "manual-upload-script",
                "type": "ai.run.artifact.registered",
                "subject": f"run/{run_id}",
                "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "datacontenttype": "application/json",
                "data": {
                    "key": f"runs/{run_id}/{filename}",
                    "size": len(file_bytes),
                    "sha256": sha256,
                    "contentType": "application/gzip",
                    "kind": "archive"
                }
            },
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        resp.raise_for_status()
        print(f"   ✓ Artifact registered")
        
        return True
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    run_id = sys.argv[1]
    explicit_dir = sys.argv[2] if len(sys.argv) > 2 else None
    control_plane_url_arg = sys.argv[3] if len(sys.argv) > 3 else None
    
    print(f"{'='*70}")
    print(f"🔧 Manual Experiment Archive Upload")
    print(f"{'='*70}")
    print(f"Run ID: {run_id}")
    
    # Find experiment directory
    experiment_dir = get_experiment_dir(run_id, explicit_dir)
    if not experiment_dir:
        sys.exit(1)
    
    print(f"Experiment dir: {experiment_dir}")
    
    # Check control plane URL (prefer arg > env var > default)
    control_plane_url = control_plane_url_arg or os.getenv("CONTROL_PLANE_URL", "http://localhost:3001")
    print(f"Control plane: {control_plane_url}")
    
    # Create archive
    try:
        archive_path = create_archive(experiment_dir)
    except Exception as e:
        print(f"❌ Failed to create archive: {e}")
        sys.exit(1)
    
    # Upload archive
    try:
        success = upload_archive_to_minio(run_id, archive_path, control_plane_url)
        os.unlink(archive_path)
        
        if success:
            print(f"\n{'='*70}")
            print(f"✅ Archive uploaded successfully!")
            print(f"{'='*70}")
            print(f"\nYou can now download the archive from the UI in:")
            print(f"  http://localhost:3001/runs/{run_id}")
            sys.exit(0)
        else:
            print(f"\n❌ Archive upload failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error during upload: {e}")
        if os.path.exists(archive_path):
            os.unlink(archive_path)
        sys.exit(1)


if __name__ == "__main__":
    main()

