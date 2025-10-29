"""
Test the complete artifact upload and retrieval flow.
This mimics EXACTLY what pod_worker does.
"""
import pytest
import os
import sys
import requests
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from event_emitter import CloudEventEmitter

CONTROL_PLANE_URL = os.environ.get("CONTROL_PLANE_URL", "http://localhost:3000")
MONGODB_URL = os.environ.get("MONGODB_URL")

@pytest.fixture
def db():
    if not MONGODB_URL:
        pytest.skip("MONGODB_URL not set")
    
    client = MongoClient(MONGODB_URL)
    database = client['ai-scientist']
    
    # Clean test data
    database['runs'].delete_many({"createdBy": "artifact_test"})
    database['artifacts'].delete_many({"runId": {"$exists": True}})  # Clean all test artifacts
    database['events'].delete_many({"source": {"$regex": "^runpod://pod/test-artifact"}})
    
    yield database
    
    # Cleanup
    database['runs'].delete_many({"createdBy": "artifact_test"})
    database['artifacts'].delete_many({"runId": {"$exists": True}})
    database['events'].delete_many({"source": {"$regex": "^runpod://pod/test-artifact"}})
    client.close()

@pytest.fixture
def test_run_id(db):
    run_id = str(uuid.uuid4())  # Real UUID for schema validation
    
    db['runs'].insert_one({
        "_id": run_id,
        "hypothesisId": str(uuid.uuid4()),
        "status": "RUNNING",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "createdBy": "artifact_test",
        "lastEventSeq": 0
    })
    
    return run_id

def test_complete_artifact_upload_flow(db, test_run_id):
    """
    Test COMPLETE artifact flow:
    1. Create fake image
    2. Upload to MinIO (via presigned URL like pod_worker)
    3. Emit artifact.registered event
    4. Verify in MongoDB
    5. Fetch via frontend API
    """
    print("\n" + "="*70)
    print("ARTIFACT UPLOAD FLOW TEST")
    print("="*70)
    
    # Step 1: Create mock image data
    print("\n📷 Step 1: Creating mock image...")
    fake_image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01' + b'\x00' * 100
    filename = "test_plot.png"
    content_type = "image/png"
    sha256 = hashlib.sha256(fake_image_data).hexdigest()
    
    print(f"   Created: {filename}")
    print(f"   Size: {len(fake_image_data)} bytes")
    print(f"   SHA256: {sha256[:16]}...")
    
    # Step 2: Request presigned URL (exactly like pod_worker)
    print("\n🔗 Step 2: Getting presigned URL from API...")
    presign_response = requests.post(
        f"{CONTROL_PLANE_URL}/api/runs/{test_run_id}/artifacts/presign",
        json={
            "action": "put",
            "filename": filename,
            "content_type": content_type
        },
        timeout=10
    )
    
    assert presign_response.status_code == 200, f"Presign failed: {presign_response.status_code} - {presign_response.text}"
    presigned_url = presign_response.json()["url"]
    
    print(f"   ✓ Got presigned URL")
    print(f"   URL: {presigned_url[:80]}...")
    
    # Step 3: Upload to MinIO (exactly like pod_worker)
    print("\n⬆️  Step 3: Uploading to MinIO...")
    upload_response = requests.put(
        presigned_url,
        data=fake_image_data,
        headers={"Content-Type": content_type},
        timeout=30
    )
    
    assert upload_response.status_code in [200, 204], f"Upload failed: {upload_response.status_code}"
    print(f"   ✓ Uploaded successfully (status: {upload_response.status_code})")
    
    # Step 4: Emit artifact.registered event (exactly like pod_worker)
    print("\n📡 Step 4: Emitting artifact.registered event...")
    emitter = CloudEventEmitter(CONTROL_PLANE_URL, "test-artifact-pod")
    
    success = emitter.artifact_registered(
        test_run_id,
        f"runs/{test_run_id}/{filename}",
        len(fake_image_data),
        sha256,
        content_type,
        "plot"
    )
    
    assert success, "Failed to emit artifact.registered event"
    print(f"   ✓ Event emitted")
    
    import time
    time.sleep(2)  # Give MongoDB time to process
    
    # Step 5: Verify in MongoDB
    print("\n💾 Step 5: Verifying in MongoDB...")
    artifact = db['artifacts'].find_one({"runId": test_run_id})
    
    assert artifact is not None, "Artifact not found in MongoDB"
    print(f"   ✓ Found in artifacts collection")
    print(f"   _id: {artifact['_id']}")
    print(f"   key: {artifact['key']}")
    print(f"   contentType: {artifact['contentType']}")
    print(f"   size: {artifact['size']} bytes")
    
    # Step 6: Test frontend fetch endpoint
    print("\n📥 Step 6: Testing frontend artifact list API...")
    list_response = requests.get(
        f"{CONTROL_PLANE_URL}/api/runs/{test_run_id}/artifacts",
        timeout=10
    )
    
    assert list_response.status_code == 200, f"List failed: {list_response.status_code}"
    artifacts_list = list_response.json()
    
    assert len(artifacts_list) >= 1, "No artifacts returned from API"
    print(f"   ✓ API returned {len(artifacts_list)} artifact(s)")
    
    fetched_artifact = artifacts_list[0]
    print(f"   Key: {fetched_artifact['key']}")
    print(f"   Type: {fetched_artifact.get('contentType')}")
    
    # Step 7: Test frontend download (presigned GET)
    print("\n⬇️  Step 7: Testing download via presigned URL...")
    download_response = requests.post(
        f"{CONTROL_PLANE_URL}/api/runs/{test_run_id}/artifacts/presign",
        json={
            "action": "get",
            "key": artifact['key']
        },
        timeout=10
    )
    
    assert download_response.status_code == 200, f"Download presign failed: {download_response.status_code}"
    download_url = download_response.json()["url"]
    
    print(f"   ✓ Got download URL")
    print(f"   URL: {download_url[:80]}...")
    
    # Actually download and verify
    print("\n✅ Step 8: Downloading and verifying...")
    file_response = requests.get(download_url, timeout=30)
    
    assert file_response.status_code == 200, f"Download failed: {file_response.status_code}"
    assert file_response.content == fake_image_data, "Downloaded content doesn't match uploaded data!"
    
    print(f"   ✓ Downloaded successfully")
    print(f"   ✓ Content matches original (SHA256 verified)")
    
    # FINAL VERIFICATION
    print("\n" + "="*70)
    print("✅ ARTIFACT FLOW COMPLETE - ALL STEPS VERIFIED")
    print("="*70)
    print("""
✓ Mock artifact created
✓ Presigned PUT URL obtained
✓ Uploaded to MinIO
✓ Event emitted and saved
✓ Artifact registered in MongoDB
✓ Frontend API lists artifacts
✓ Presigned GET URL works
✓ File downloaded and verified

THE COMPLETE ARTIFACT FLOW WORKS END-TO-END!
Pod worker will successfully upload artifacts and frontend will display them.
    """)

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

