import pytest
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient
from ulid import ULID

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

@pytest.fixture
def mongo_client():
    url = os.environ.get('MONGODB_URL')
    if not url:
        pytest.skip("MONGODB_URL not set")
    client = MongoClient(url)
    yield client
    client.close()

@pytest.fixture
def test_db(mongo_client):
    db = mongo_client['ai-scientist-test']
    yield db
    mongo_client.drop_database('ai-scientist-test')

@pytest.fixture
def mock_hypothesis(test_db):
    hypothesis_id = str(ULID())
    hypothesis = {
        "_id": hypothesis_id,
        "title": "Test Hypothesis",
        "idea": "A simple test idea for validation",
        "ideaJson": {
            "Name": "test_experiment",
            "Title": "Test Experiment",
            "Short Hypothesis": "This is a test",
            "Abstract": "Testing the pipeline with a minimal experiment",
            "Experiments": [
                "Run a simple PyTorch model",
                "Measure accuracy"
            ],
            "Risk Factors and Limitations": [
                "This is just a test"
            ]
        },
        "createdAt": datetime.utcnow(),
        "createdBy": "test"
    }
    test_db['hypotheses'].insert_one(hypothesis)
    return hypothesis

@pytest.fixture
def mock_run(test_db, mock_hypothesis):
    run_id = str(ULID())
    run = {
        "_id": run_id,
        "hypothesisId": mock_hypothesis["_id"],
        "status": "QUEUED",
        "claimedBy": None,
        "createdAt": datetime.utcnow()
    }
    test_db['runs'].insert_one(run)
    return run

def test_event_emission(test_db, mock_run):
    from pod_worker import EventEmitter
    
    emitter = EventEmitter("http://localhost:3000", "test-pod")
    
    emitter.emit("ai.run.started", {
        "run_id": mock_run["_id"],
        "pod_id": "test-pod",
        "gpu": "Test GPU",
        "region": "test",
        "image": "test:latest"
    }, mock_run["_id"])
    
    emitter.flush()
    
    time.sleep(1)
    events = list(test_db['events'].find({"runId": mock_run["_id"]}))
    assert len(events) > 0, "Events should be saved to database"

def test_run_status_transitions(test_db, mock_run):
    transitions = []
    
    test_db['runs'].update_one(
        {"_id": mock_run["_id"]},
        {"$set": {"status": "SCHEDULED"}}
    )
    transitions.append(test_db['runs'].find_one({"_id": mock_run["_id"]})['status'])
    
    test_db['runs'].update_one(
        {"_id": mock_run["_id"]},
        {"$set": {"status": "RUNNING"}}
    )
    transitions.append(test_db['runs'].find_one({"_id": mock_run["_id"]})['status'])
    
    test_db['runs'].update_one(
        {"_id": mock_run["_id"]},
        {"$set": {"status": "COMPLETED"}}
    )
    transitions.append(test_db['runs'].find_one({"_id": mock_run["_id"]})['status'])
    
    assert transitions == ["SCHEDULED", "RUNNING", "COMPLETED"]

def test_stage_progress_tracking(test_db, mock_run):
    for i, stage in enumerate(["Stage_1", "Stage_2", "Stage_3", "Stage_4"]):
        test_db['runs'].update_one(
            {"_id": mock_run["_id"]},
            {"$set": {
                "currentStage": {
                    "name": stage,
                    "progress": (i + 1) / 4.0
                },
                f"stageTiming.{stage}.elapsed_s": 300 * (i + 1)
            }}
        )
    
    run = test_db['runs'].find_one({"_id": mock_run["_id"]})
    assert run['currentStage']['name'] == 'Stage_4'
    assert run['currentStage']['progress'] == 1.0
    assert 'stageTiming' in run
    assert run['stageTiming']['Stage_1']['elapsed_s'] == 300

def test_error_handling(test_db, mock_run):
    error_info = {
        "errorType": "ValueError",
        "errorMessage": "Test error message",
        "status": "FAILED"
    }
    
    test_db['runs'].update_one(
        {"_id": mock_run["_id"]},
        {"$set": error_info}
    )
    
    run = test_db['runs'].find_one({"_id": mock_run["_id"]})
    assert run['status'] == 'FAILED'
    assert run['errorType'] == 'ValueError'
    assert run['errorMessage'] == 'Test error message'

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

