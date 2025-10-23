#!/usr/bin/env python3
"""
Helper script to upload artifacts after paper generation.
Called automatically by retry-writeup wrapper script.
"""
import os
import sys
import hashlib
import requests
from pathlib import Path

def upload_paper_artifact(run_id: str, pdf_path: str, control_plane_url: str):
    """Upload paper PDF as artifact"""
    try:
        filename = os.path.basename(pdf_path)
        
        # Get presigned URL
        resp = requests.post(
            f"{control_plane_url}/api/runs/{run_id}/artifacts/presign",
            json={"action": "put", "filename": filename, "content_type": "application/pdf"},
            timeout=30
        )
        resp.raise_for_status()
        presigned_url = resp.json()["url"]
        
        # Upload file
        with open(pdf_path, "rb") as f:
            file_bytes = f.read()
        
        resp = requests.put(presigned_url, data=file_bytes, timeout=300)
        resp.raise_for_status()
        
        # Calculate SHA256
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        
        # Register artifact
        resp = requests.post(
            f"{control_plane_url}/api/ingest/event",
            json={
                "specversion": "1.0",
                "id": f"artifact-{run_id}-{filename}",
                "source": "writeup-retry",
                "type": "ai.run.artifact.registered",
                "subject": f"run/{run_id}",
                "time": "",
                "datacontenttype": "application/json",
                "data": {
                    "key": f"runs/{run_id}/{filename}",
                    "size": len(file_bytes),
                    "sha256": sha256,
                    "contentType": "application/pdf",
                    "kind": "paper"
                }
            },
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        resp.raise_for_status()
        
        print(f"✅ Uploaded paper artifact: {filename}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to upload artifact: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: upload_artifact_helper.py <run_id> <pdf_path> <control_plane_url>")
        sys.exit(1)
    
    run_id = sys.argv[1]
    pdf_path = sys.argv[2]
    control_plane_url = sys.argv[3]
    
    success = upload_paper_artifact(run_id, pdf_path, control_plane_url)
    sys.exit(0 if success else 1)

