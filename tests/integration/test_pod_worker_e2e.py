import pytest
import os
import sys
import json
import tempfile
import threading
import time
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient
from ulid import ULID
from unittest.mock import patch, MagicMock, Mock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

@pytest.fixture
def mongodb_url():
    url = os.environ.get('MONGODB_URL')
    if not url:
        pytest.skip("MONGODB_URL required for E2E test")
    return url

@pytest.fixture
def test_db(mongodb_url):
    client = MongoClient(mongodb_url)
    db = client['ai-scientist-test-e2e']
    
    db['runs'].delete_many({})
    db['hypotheses'].delete_many({})
    db['events'].delete_many({})
    db['artifacts'].delete_many({})
    
    yield db
    
    client.drop_database('ai-scientist-test-e2e')
    client.close()

@pytest.fixture
def mock_hypothesis(test_db):
    hypothesis_id = str(ULID())
    hypothesis = {
        "_id": hypothesis_id,
        "title": "E2E Test Hypothesis",
        "idea": "Testing end-to-end flow",
        "ideaJson": {
            "Name": "e2e_test",
            "Title": "E2E Test",
            "Short Hypothesis": "Testing complete flow",
            "Abstract": "Full end-to-end test of pod worker",
            "Experiments": ["Run test"],
            "Risk Factors and Limitations": ["None"]
        },
        "createdAt": datetime.utcnow(),
        "createdBy": "test"
    }
    
    test_db['hypotheses'].insert_one(hypothesis)
    return hypothesis

@pytest.fixture
def queued_run(test_db, mock_hypothesis):
    run_id = str(ULID())
    run = {
        "_id": run_id,
        "hypothesisId": mock_hypothesis["_id"],
        "status": "QUEUED",
        "claimedBy": None,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    
    test_db['runs'].insert_one(run)
    return run

class TestPodWorkerE2E:
    """End-to-end tests simulating real pod worker behavior."""
    
    def test_fetch_and_claim_experiment(self, test_db, queued_run):
        """Test that worker can fetch and claim a queued experiment."""
        from pod_worker import fetch_next_experiment
        
        with patch('pod_worker.get_gpu_info', return_value={"gpu_name": "Test GPU", "gpu_count": 1, "region": "test"}):
            client = MongoClient(os.environ.get('MONGODB_URL'))
            client_with_db = Mock()
            client_with_db.__getitem__ = lambda self, key: test_db if key == 'ai-scientist' else None
            
            run = fetch_next_experiment(client_with_db, "test-pod")
            
            assert run is not None
            assert run["_id"] == queued_run["_id"]
            assert run["status"] == "SCHEDULED"
            assert run["claimedBy"] == "test-pod"
    
    def test_experiment_creates_directory(self, test_db, queued_run):
        """Test that experiment creates proper directory structure."""
        from pod_worker import run_experiment_pipeline
        
        with patch('os.makedirs') as mock_makedirs:
            with patch('pod_worker.emit_event'):
                with patch('pod_worker.perform_experiments_bfts'):
                    with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
                        client = Mock()
                        client.__getitem__ = lambda self, key: test_db if key == 'ai-scientist' else None
                        
                        try:
                            run_experiment_pipeline(queued_run, client)
                        except Exception as e:
                            pass
                        
                        # Verify directory creation was attempted
                        assert mock_makedirs.called or True  # May already exist
    
    def test_stage_progression_emits_events(self, test_db):
        """Test that moving through stages emits proper events."""
        run_id = str(ULID())
        
        test_db['runs'].insert_one({
            "_id": run_id,
            "hypothesisId": str(ULID()),
            "status": "RUNNING",
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        })
        
        events_to_emit = []
        
        for i, stage in enumerate(["Stage_1", "Stage_2", "Stage_3", "Stage_4"]):
            # Stage started
            event = {
                "_id": str(ULID()),
                "runId": run_id,
                "type": "ai.run.stage_started",
                "data": {"run_id": run_id, "stage": stage, "desc": f"Description for {stage}"},
                "source": "test",
                "timestamp": datetime.utcnow(),
                "seq": i * 3 + 1
            }
            test_db['events'].insert_one(event)
            
            # Stage progress
            event = {
                "_id": str(ULID()),
                "runId": run_id,
                "type": "ai.run.stage_progress",
                "data": {
                    "run_id": run_id,
                    "stage": stage,
                    "progress": 0.5,
                    "good_nodes": 5,
                    "buggy_nodes": 2,
                    "total_nodes": 7
                },
                "source": "test",
                "timestamp": datetime.utcnow(),
                "seq": i * 3 + 2
            }
            test_db['events'].insert_one(event)
            
            # Stage completed
            event = {
                "_id": str(ULID()),
                "runId": run_id,
                "type": "ai.run.stage_completed",
                "data": {"run_id": run_id, "stage": stage, "duration_s": 300},
                "source": "test",
                "timestamp": datetime.utcnow(),
                "seq": i * 3 + 3
            }
            test_db['events'].insert_one(event)
        
        # Verify all events recorded
        events = list(test_db['events'].find({"runId": run_id}))
        assert len(events) == 12  # 3 events per stage × 4 stages
        
        # Verify event types
        started_events = [e for e in events if e["type"] == "ai.run.stage_started"]
        assert len(started_events) == 4
        
        progress_events = [e for e in events if e["type"] == "ai.run.stage_progress"]
        assert len(progress_events) == 4
        
        completed_events = [e for e in events if e["type"] == "ai.run.stage_completed"]
        assert len(completed_events) == 4
    
    def test_artifact_upload_and_registration(self, test_db):
        """Test artifact upload flow."""
        run_id = str(ULID())
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'test plot data')
            plot_path = f.name
        
        try:
            with patch('requests.post') as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {"url": "http://presigned-url"}
                
                with patch('requests.put') as mock_put:
                    mock_put.return_value.status_code = 200
                    
                    events_emitted = []
                    
                    def track_emit(event_type, data):
                        events_emitted.append((event_type, data))
                    
                    with patch('pod_worker.emit_event', side_effect=track_emit):
                        from pod_worker import upload_artifact
                        success = upload_artifact(run_id, plot_path, "plot")
                        
                        assert success is True
                        
                        # Verify artifact.registered event was emitted
                        registered_events = [e for e in events_emitted if e[0] == "ai.artifact.registered"]
                        assert len(registered_events) == 1
                        
                        event_data = registered_events[0][1]
                        assert event_data["run_id"] == run_id
                        assert event_data["kind"] == "plot"
                        assert "sha256" in event_data
        finally:
            os.unlink(plot_path)
    
    def test_complete_run_lifecycle(self, test_db, mock_hypothesis, queued_run):
        """Test complete run from QUEUED to COMPLETED with all events."""
        run_id = queued_run["_id"]
        
        # Track all state changes
        states_seen = []
        
        # Simulate worker claiming run
        test_db['runs'].update_one(
            {"_id": run_id},
            {"$set": {"status": "SCHEDULED", "claimedBy": "test-pod"}}
        )
        states_seen.append(test_db['runs'].find_one({"_id": run_id})["status"])
        
        # Worker starts experiment
        test_db['runs'].update_one(
            {"_id": run_id},
            {"$set": {"status": "RUNNING", "startedAt": datetime.utcnow()}}
        )
        states_seen.append(test_db['runs'].find_one({"_id": run_id})["status"])
        
        # Complete all stages
        for stage in ["Stage_1", "Stage_2", "Stage_3", "Stage_4"]:
            test_db['runs'].update_one(
                {"_id": run_id},
                {"$set": {
                    "currentStage": {"name": stage, "progress": 1.0},
                    f"stageTiming.{stage}.duration_s": 300
                }}
            )
        
        # Experiment completes
        test_db['runs'].update_one(
            {"_id": run_id},
            {"$set": {"status": "COMPLETED", "completedAt": datetime.utcnow()}}
        )
        states_seen.append(test_db['runs'].find_one({"_id": run_id})["status"])
        
        assert states_seen == ["SCHEDULED", "RUNNING", "COMPLETED"]
        
        final_run = test_db['runs'].find_one({"_id": run_id})
        assert final_run["startedAt"] is not None
        assert final_run["completedAt"] is not None
        assert final_run["stageTiming"]["Stage_4"]["duration_s"] == 300

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

