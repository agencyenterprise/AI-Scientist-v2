"""
Integration test that validates ALL events can be sent to the API and saved to MongoDB.
Tests every event type the pod worker emits.
"""
import pytest
import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient
import uuid

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

CONTROL_PLANE_URL = os.environ.get("CONTROL_PLANE_URL", "http://localhost:3000")
MONGODB_URL = os.environ.get("MONGODB_URL")

@pytest.fixture
def mongodb():
    if not MONGODB_URL:
        pytest.skip("MONGODB_URL not set")
    client = MongoClient(MONGODB_URL)
    
    # Use same database as production
    db = client['ai-scientist']
    
    # Clean up test data (be careful not to delete real data)
    # Only delete runs created by tests
    db['runs'].delete_many({"createdBy": "test"})
    db['events'].delete_many({"source": {"$regex": "^test://"}})
    db['hypotheses'].delete_many({"createdBy": "test"})
    
    yield db
    
    # Cleanup after test
    db['runs'].delete_many({"createdBy": "test"})
    db['events'].delete_many({"source": {"$regex": "^test://"}})
    db['hypotheses'].delete_many({"createdBy": "test"})
    client.close()

@pytest.fixture
def test_run(mongodb):
    run_id = str(uuid.uuid4())
    hypothesis_id = str(uuid.uuid4())
    
    mongodb['hypotheses'].insert_one({
        "_id": hypothesis_id,
        "title": "Test",
        "idea": "Test",
        "ideaJson": {},
        "createdAt": datetime.utcnow(),
        "createdBy": "test"
    })
    
    mongodb['runs'].insert_one({
        "_id": run_id,
        "hypothesisId": hypothesis_id,
        "status": "QUEUED",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "createdBy": "test"
    })
    
    return run_id

def create_event(event_type: str, run_id: str, data: dict, seq: int = 1):
    """Create a properly formatted CloudEvents envelope."""
    return {
        "specversion": "1.0",
        "id": str(uuid.uuid4()),
        "source": f"test://pod/test-pod",
        "type": event_type,
        "subject": f"run/{run_id}",
        "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datacontenttype": "application/json",
        "data": data,
        "extensions": {"seq": seq}
    }

def send_event(event: dict) -> requests.Response:
    """Send event to control plane API."""
    response = requests.post(
        f"{CONTROL_PLANE_URL}/api/ingest/event",
        json=event,
        timeout=10
    )
    return response

class TestEventAPIValidation:
    """Test that all event types can be sent successfully."""
    
    def test_run_started_event(self, mongodb, test_run):
        """Test ai.run.started event."""
        # Set run to SCHEDULED first (as worker does when it claims)
        mongodb['runs'].update_one(
            {"_id": test_run},
            {"$set": {"status": "SCHEDULED", "claimedBy": "test-pod", "lastEventSeq": 0}}
        )
        
        event = create_event("ai.run.started", test_run, {
            "run_id": test_run,
            "pod_id": "test-pod",
            "gpu": "NVIDIA L40S",
            "region": "us-west",
            "image": "test:latest"
        })
        
        print(f"\n📤 Sending event to {CONTROL_PLANE_URL}/api/ingest/event")
        print(f"Event: {json.dumps(event, indent=2, default=str)}")
        
        response = send_event(event)
        print(f"\n📥 Response: {response.status_code}")
        print(f"Body: {response.text}")
        
        assert response.status_code == 201, f"Failed: {response.status_code} - {response.text}"
        
        import time
        time.sleep(2)  # Give it time to process
        
        # Verify saved to MongoDB
        print(f"\n🔍 Checking MongoDB for event...")
        saved_event = mongodb['events'].find_one({"runId": test_run, "type": "ai.run.started"})
        
        if saved_event:
            print(f"✓ Found event in MongoDB")
        else:
            # Debug: check what's in the events collection
            all_events = list(mongodb['events'].find({}))
            print(f"❌ Event not found. Total events in DB: {len(all_events)}")
            for evt in all_events[:3]:
                print(f"  - {evt.get('type')} for run {evt.get('runId')}")
        
        assert saved_event is not None
        
        # Verify run status updated
        run = mongodb['runs'].find_one({"_id": test_run})
        assert run['status'] == 'RUNNING'
        assert run.get('startedAt') is not None
    
    def test_stage_started_event(self, mongodb, test_run):
        """Test ai.run.stage_started event."""
        # Set run to RUNNING first
        mongodb['runs'].update_one(
            {"_id": test_run},
            {"$set": {"status": "RUNNING", "lastEventSeq": 0}}
        )
        
        event = create_event("ai.run.stage_started", test_run, {
            "run_id": test_run,
            "stage": "Stage_1",
            "desc": "Preliminary Investigation"
        }, seq=1)
        
        response = send_event(event)
        assert response.status_code == 201, f"Failed: {response.status_code} - {response.text}"
        
        saved_event = mongodb['events'].find_one({"runId": test_run, "type": "ai.run.stage_started"})
        assert saved_event is not None
        
        run = mongodb['runs'].find_one({"_id": test_run})
        assert run.get('currentStage', {}).get('name') == 'Stage_1'
    
    def test_stage_progress_event(self, mongodb, test_run):
        """Test ai.run.stage_progress event with ALL fields."""
        mongodb['runs'].update_one(
            {"_id": test_run},
            {"$set": {"status": "RUNNING", "lastEventSeq": 0, "currentStage": {"name": "Stage_1", "progress": 0}}}
        )
        
        event = create_event("ai.run.stage_progress", test_run, {
            "run_id": test_run,
            "stage": "Stage_1",
            "progress": 0.21,
            "eta_s": 1200,
            "iteration": 3,
            "max_iterations": 14,
            "good_nodes": 3,
            "buggy_nodes": 1,
            "total_nodes": 4,
            "best_metric": "loss=0.0184"
        }, seq=1)
        
        response = send_event(event)
        assert response.status_code == 201, f"Failed: {response.status_code} - {response.text}"
        
        run = mongodb['runs'].find_one({"_id": test_run})
        stage = run.get('currentStage', {})
        
        assert stage.get('progress') == 0.21
        assert stage.get('iteration') == 3
        assert stage.get('maxIterations') == 14
        assert stage.get('goodNodes') == 3
        assert stage.get('buggyNodes') == 1
        assert stage.get('totalNodes') == 4
        assert stage.get('bestMetric') == "loss=0.0184"
    
    def test_stage_completed_event(self, mongodb, test_run):
        """Test ai.run.stage_completed event."""
        mongodb['runs'].update_one(
            {"_id": test_run},
            {"$set": {"status": "RUNNING", "lastEventSeq": 0}}
        )
        
        event = create_event("ai.run.stage_completed", test_run, {
            "run_id": test_run,
            "stage": "Stage_1",
            "duration_s": 720
        }, seq=1)
        
        response = send_event(event)
        assert response.status_code == 201, f"Failed: {response.status_code} - {response.text}"
        
        # Should update stageTiming
        run = mongodb['runs'].find_one({"_id": test_run})
        # Note: This requires the event handler to save timing
    
    def test_run_log_event(self, mongodb, test_run):
        """Test ai.run.log event."""
        mongodb['runs'].update_one(
            {"_id": test_run},
            {"$set": {"status": "RUNNING", "lastEventSeq": 0}}
        )
        
        event = create_event("ai.run.log", test_run, {
            "run_id": test_run,
            "message": "Stage_1: 3/14 good nodes [12m 34s]",
            "level": "info"
        }, seq=1)
        
        response = send_event(event)
        assert response.status_code == 201, f"Failed: {response.status_code} - {response.text}"
        
        saved_event = mongodb['events'].find_one({"runId": test_run, "type": "ai.run.log"})
        assert saved_event is not None
        assert saved_event['data']['message'] == "Stage_1: 3/14 good nodes [12m 34s]"
        assert saved_event['data']['level'] == "info"
    
    def test_run_failed_event(self, mongodb, test_run):
        """Test ai.run.failed event."""
        mongodb['runs'].update_one(
            {"_id": test_run},
            {"$set": {"status": "RUNNING", "lastEventSeq": 0}}
        )
        
        event = create_event("ai.run.failed", test_run, {
            "run_id": test_run,
            "stage": "Stage_1",
            "code": "AuthenticationError",
            "message": "Invalid API key",
            "traceback": "Traceback...",
            "retryable": False
        }, seq=1)
        
        response = send_event(event)
        assert response.status_code == 201, f"Failed: {response.status_code} - {response.text}"
        
        run = mongodb['runs'].find_one({"_id": test_run})
        assert run['status'] == 'FAILED'
        assert run.get('errorType') == 'AuthenticationError'
        assert run.get('errorMessage') == 'Invalid API key'
        assert run.get('failedAt') is not None
    
    def test_artifact_registered_event(self, mongodb, test_run):
        """Test ai.artifact.registered event."""
        mongodb['runs'].update_one(
            {"_id": test_run},
            {"$set": {"status": "RUNNING", "lastEventSeq": 0}}
        )
        
        event = create_event("ai.artifact.registered", test_run, {
            "run_id": test_run,
            "key": f"runs/{test_run}/plot.png",
            "bytes": 12345,
            "sha256": "abc123",
            "content_type": "image/png",
            "kind": "plot"
        }, seq=1)
        
        response = send_event(event)
        assert response.status_code == 201, f"Failed: {response.status_code} - {response.text}"
        
        artifact = mongodb['artifacts'].find_one({"runId": test_run})
        assert artifact is not None
        assert artifact['contentType'] == 'image/png'

class TestCompleteEventSequence:
    """Test a complete sequence of events as they would happen in real run."""
    
    def test_complete_stage_1_flow(self, mongodb, test_run):
        """Test complete Stage 1 flow with all events."""
        
        events_to_send = [
            # Run started
            ("ai.run.started", {
                "run_id": test_run,
                "pod_id": "test-pod",
                "gpu": "NVIDIA L40S",
                "region": "us-west",
                "image": "test:latest"
            }),
            
            # Stage 1 started
            ("ai.run.stage_started", {
                "run_id": test_run,
                "stage": "Stage_1",
                "desc": "Preliminary Investigation"
            }),
            
            # Progress update 1
            ("ai.run.stage_progress", {
                "run_id": test_run,
                "stage": "Stage_1",
                "progress": 0.07,
                "iteration": 1,
                "max_iterations": 14,
                "good_nodes": 1,
                "buggy_nodes": 0,
                "total_nodes": 1,
                "best_metric": "loss=0.025"
            }),
            
            # Log message
            ("ai.run.log", {
                "run_id": test_run,
                "message": "Stage_1: iteration 1/14 completed [1m 23s]",
                "level": "info"
            }),
            
            # Progress update 2
            ("ai.run.stage_progress", {
                "run_id": test_run,
                "stage": "Stage_1",
                "progress": 0.21,
                "iteration": 3,
                "max_iterations": 14,
                "good_nodes": 3,
                "buggy_nodes": 1,
                "total_nodes": 4,
                "best_metric": "loss=0.0184",
                "eta_s": 900
            }),
            
            # Stage completed
            ("ai.run.stage_completed", {
                "run_id": test_run,
                "stage": "Stage_1",
                "duration_s": 720
            }),
        ]
        
        for seq, (event_type, data) in enumerate(events_to_send, start=1):
            event = create_event(event_type, test_run, data, seq)
            response = send_event(event)
            
            assert response.status_code == 201, \
                f"Event {event_type} failed: {response.status_code} - {response.text}"
            
            print(f"✓ {event_type} sent successfully")
        
        # Verify final state
        run = mongodb['runs'].find_one({"_id": test_run})
        
        print("\n✅ Final run state:")
        print(f"   Status: {run.get('status')}")
        print(f"   CurrentStage: {run.get('currentStage')}")
        print(f"   StageTiming: {run.get('stageTiming')}")
        print(f"   LastEventSeq: {run.get('lastEventSeq')}")
        
        # Verify all events saved
        events = list(mongodb['events'].find({"runId": test_run}))
        assert len(events) == len(events_to_send)
        
        print(f"\n✅ All {len(events)} events saved to MongoDB")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

