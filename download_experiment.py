#!/usr/bin/env python3
"""
Download and extract an experiment archive from MinIO
"""
import os
import sys
import requests
import tempfile
import tarfile
from pathlib import Path

# Configuration
CONTROL_PLANE_URL = os.environ.get("CONTROL_PLANE_URL", "https://ai-scientist-v2-production.up.railway.app")

def download_experiment(run_id: str):
    """Download and extract an experiment from MinIO"""
    
    print(f"📦 Downloading experiment: {run_id}")
    
    # Get artifacts from API
    print(f"🔍 Fetching artifact list from API...")
    resp = requests.get(
        f"{CONTROL_PLANE_URL}/api/runs/{run_id}",
        timeout=30
    )
    resp.raise_for_status()
    run_data = resp.json()
    
    artifacts = run_data.get("artifacts", [])
    if not artifacts:
        print(f"❌ No artifacts found for run {run_id}")
        return None
    
    # Find the archive artifact
    archive_artifact = None
    for artifact in artifacts:
        if "archive" in artifact.get("key", ""):
            archive_artifact = artifact
            break
    
    if not archive_artifact:
        print(f"❌ No archive artifact found for run {run_id}")
        print(f"Available artifacts:")
        for artifact in artifacts:
            print(f"  - {artifact.get('kind', 'unknown')}: {artifact.get('key', 'no key')}")
        return None
    
    archive_key = archive_artifact["key"]
    print(f"✓ Found archive: {archive_key}")
    
    # Get presigned download URL
    print(f"📥 Requesting download URL...")
    resp = requests.post(
        f"{CONTROL_PLANE_URL}/api/runs/{run_id}/artifacts/presign",
        json={"action": "get", "key": archive_key},
        timeout=30
    )
    resp.raise_for_status()
    download_url = resp.json()["url"]
    
    # Download the archive
    print(f"⬇️  Downloading archive...")
    archive_resp = requests.get(download_url, timeout=300)
    archive_resp.raise_for_status()
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
        tmp.write(archive_resp.content)
        tmp_path = tmp.name
    
    print(f"✓ Downloaded {len(archive_resp.content)} bytes")
    
    # Extract to experiments directory
    experiments_dir = Path("experiments")
    experiments_dir.mkdir(exist_ok=True)
    
    print(f"📂 Extracting to experiments/...")
    with tarfile.open(tmp_path, 'r:gz') as tar:
        tar.extractall(experiments_dir)
    
    # Clean up temp file
    os.unlink(tmp_path)
    
    # Find the extracted directory
    extracted_dirs = sorted([d for d in experiments_dir.iterdir() if d.is_dir() and run_id in d.name])
    
    if extracted_dirs:
        extracted_dir = extracted_dirs[0]
        print(f"✓ Extracted to: {extracted_dir}")
        
        # Check for PDF files
        pdf_files = list(extracted_dir.rglob("*.pdf"))
        if pdf_files:
            print(f"\n📄 Found {len(pdf_files)} PDF file(s):")
            for pdf in pdf_files:
                print(f"   - {pdf.relative_to(experiments_dir)}")
        else:
            print(f"\n⚠️  No PDF files found in the archive")
        
        return extracted_dir
    else:
        print(f"⚠️  Could not find extracted directory")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python download_experiment.py <run_id>")
        sys.exit(1)
    
    run_id = sys.argv[1]
    
    try:
        result = download_experiment(run_id)
        if result:
            print(f"\n✅ Success! Experiment downloaded to: {result}")
        else:
            print(f"\n❌ Failed to download experiment")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

