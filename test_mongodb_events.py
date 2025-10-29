#!/usr/bin/env python3
"""
Test script to verify events are being created in MongoDB correctly.
Sends test events and checks MongoDB to confirm they were stored.
"""

import os
import sys
import time
import requests
from datetime import datetime
from pymongo import MongoClient
from ulid import ULID

CONTROL_PLANE_URL = os.environ.get("CONTROL_PLANE_URL", "https://ai-scientist-v2-production.up.railway.app")
MONGODB_URL = os.environ.get("MONGODB_URL", "")

if not MONGODB_URL:
    print("❌ MONGODB_URL environment variable not set", file=sys.stderr)
    print("Set it with: export MONGODB_URL='mongodb://...'")
    sys.exit(1)


def connect_mongodb():
    """Connect to MongoDB"""
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
        
        return client[db_name]
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}", file=sys.stderr)
        sys.exit(1)


def send_test_event(event_id, run_id, event_type, data):
    """Send a test event to the backend"""
    event = {
        "specversion": "1.0",
        "id": event_id,
        "source": "test://mongodb-test",
        "type": event_type,
        "subject": f"run/{run_id}",
        "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datacontenttype": "application/json",
        "data": data,
        "extensions": {
            "seq": 1
        }
    }
    
    response = requests.post(
        f"{CONTROL_PLANE_URL}/api/ingest/event",
        json=event,
        headers={"Content-Type": "application/cloudevents+json"},
        timeout=10
    )
    
    return response


def test_event_stored_in_mongodb():
    """Test that events are stored in MongoDB events collection"""
    print("="*60)
    print("Test 1: Verify Event Stored in MongoDB")
    print("="*60 + "\n")
    
    db = connect_mongodb()
    events_collection = db["events"]
    
    # Generate unique IDs
    event_id = str(ULID())
    run_id = str(ULID())
    
    # Count events before
    count_before = events_collection.count_documents({"_id": event_id})
    
    print(f"Sending test event...")
    print(f"  Event ID: {event_id}")
    print(f"  Run ID: {run_id}")
    print(f"  Type: ai.run.heartbeat\n")
    
    # Send event
    response = send_test_event(
        event_id=event_id,
        run_id=run_id,
        event_type="ai.run.heartbeat",
        data={"run_id": run_id, "gpu_util": 0.75}
    )
    
    print(f"Response: {response.status_code} - {response.json()}\n")
    
    if response.status_code != 201:
        print(f"❌ Event ingestion failed")
        return False
    
    # Wait a moment for processing
    time.sleep(2)
    
    # Check if event exists in MongoDB
    event_doc = events_collection.find_one({"_id": event_id})
    
    if not event_doc:
        print(f"❌ Event NOT found in MongoDB events collection")
        return False
    
    print(f"✅ Event found in MongoDB!")
    print(f"\nEvent document:")
    print(f"  _id: {event_doc['_id']}")
    print(f"  runId: {event_doc['runId']}")
    print(f"  type: {event_doc['type']}")
    print(f"  source: {event_doc['source']}")
    print(f"  timestamp: {event_doc['timestamp']}")
    print(f"  seq: {event_doc.get('seq', 'N/A')}")
    print(f"  data: {event_doc['data']}")
    
    return True


def test_event_deduplication():
    """Test that duplicate events are ignored"""
    print("\n" + "="*60)
    print("Test 2: Verify Event Deduplication")
    print("="*60 + "\n")
    
    db = connect_mongodb()
    events_collection = db["events"]
    events_seen_collection = db["events_seen"]
    
    # Generate unique IDs
    event_id = str(ULID())
    run_id = str(ULID())
    
    print(f"Sending event first time...")
    print(f"  Event ID: {event_id}\n")
    
    # Send first time
    response1 = send_test_event(
        event_id=event_id,
        run_id=run_id,
        event_type="ai.run.heartbeat",
        data={"run_id": run_id, "gpu_util": 0.80}
    )
    
    print(f"Response 1: {response1.status_code} - {response1.json()}\n")
    
    time.sleep(1)
    
    # Check events_seen collection
    seen_doc = events_seen_collection.find_one({"_id": event_id})
    
    if not seen_doc:
        print(f"❌ Event NOT tracked in events_seen collection")
        return False
    
    print(f"✅ Event tracked in events_seen collection")
    print(f"  Processed at: {seen_doc['processedAt']}")
    print(f"  Run ID: {seen_doc['runId']}\n")
    
    # Send same event again
    print(f"Sending SAME event again (should be duplicate)...\n")
    
    response2 = send_test_event(
        event_id=event_id,  # Same ID!
        run_id=run_id,
        event_type="ai.run.heartbeat",
        data={"run_id": run_id, "gpu_util": 0.85}
    )
    
    print(f"Response 2: {response2.status_code} - {response2.json()}\n")
    
    if response2.status_code == 201 and response2.json().get("status") == "duplicate":
        print(f"✅ Duplicate detected correctly!")
        return True
    else:
        print(f"❌ Duplicate detection failed")
        return False


def test_stage_events_create_stages():
    """Test that stage events create stage documents"""
    print("\n" + "="*60)
    print("Test 3: Verify Stage Events Create Stage Documents")
    print("="*60 + "\n")
    
    db = connect_mongodb()
    stages_collection = db["stages"]
    
    # Generate unique IDs
    event_id = str(ULID())
    run_id = str(ULID())
    stage_id = f"{run_id}-Stage_1"
    
    print(f"Sending ai.run.stage_started event...")
    print(f"  Run ID: {run_id}")
    print(f"  Stage: Stage_1\n")
    
    # Send stage started event
    response = send_test_event(
        event_id=event_id,
        run_id=run_id,
        event_type="ai.run.stage_started",
        data={
            "run_id": run_id,
            "stage": "Stage_1",
            "desc": "Test Stage"
        }
    )
    
    print(f"Response: {response.status_code} - {response.json()}\n")
    
    time.sleep(2)
    
    # Check if stage was created
    stage_doc = stages_collection.find_one({"_id": stage_id})
    
    if not stage_doc:
        print(f"❌ Stage document NOT created in MongoDB")
        return False
    
    print(f"✅ Stage document created!")
    print(f"\nStage document:")
    print(f"  _id: {stage_doc['_id']}")
    print(f"  runId: {stage_doc['runId']}")
    print(f"  name: {stage_doc['name']}")
    print(f"  status: {stage_doc['status']}")
    print(f"  progress: {stage_doc['progress']}")
    print(f"  startedAt: {stage_doc.get('startedAt', 'N/A')}")
    
    return True


def test_run_status_transitions():
    """Test that events trigger run status transitions"""
    print("\n" + "="*60)
    print("Test 4: Verify Run Status Transitions")
    print("="*60 + "\n")
    
    db = connect_mongodb()
    runs_collection = db["runs"]
    
    # Create a test run manually
    run_id = str(ULID())
    hypothesis_id = str(ULID())
    
    print(f"Creating test run in MongoDB...")
    print(f"  Run ID: {run_id}\n")
    
    runs_collection.insert_one({
        "_id": run_id,
        "hypothesisId": hypothesis_id,
        "status": "QUEUED",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })
    
    # Send ai.run.started event
    print(f"Sending ai.run.started event...\n")
    
    event_id = str(ULID())
    response = send_test_event(
        event_id=event_id,
        run_id=run_id,
        event_type="ai.run.started",
        data={
            "run_id": run_id,
            "pod_id": "test-pod",
            "gpu": "Test GPU"
        }
    )
    
    print(f"Response: {response.status_code} - {response.json()}\n")
    
    time.sleep(2)
    
    # Check if run status changed
    run_doc = runs_collection.find_one({"_id": run_id})
    
    if not run_doc:
        print(f"❌ Run not found in MongoDB")
        return False
    
    if run_doc["status"] != "RUNNING":
        print(f"❌ Run status not updated (expected RUNNING, got {run_doc['status']})")
        return False
    
    print(f"✅ Run status transitioned correctly!")
    print(f"  Status: {run_doc['status']}")
    print(f"  Pod ID: {run_doc.get('pod', {}).get('id', 'N/A')}")
    print(f"  Last Event Seq: {run_doc.get('lastEventSeq', 'N/A')}")
    
    # Cleanup
    runs_collection.delete_one({"_id": run_id})
    
    return True


def main():
    print("\n" + "="*60)
    print("MongoDB Event Storage Tests")
    print(f"Control Plane: {CONTROL_PLANE_URL}")
    print("="*60 + "\n")
    
    results = []
    
    try:
        results.append(("Event Stored in MongoDB", test_event_stored_in_mongodb()))
        results.append(("Event Deduplication", test_event_deduplication()))
        results.append(("Stage Creation", test_stage_events_create_stages()))
        results.append(("Run Status Transitions", test_run_status_transitions()))
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Could not connect to {CONTROL_PLANE_URL}")
        print("Make sure the control plane is running and accessible.")
        return
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60 + "\n")
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name:30s} {status}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED")
        print("\nEvents are correctly stored in MongoDB!")
    else:
        print("⚠ SOME TESTS FAILED")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()

