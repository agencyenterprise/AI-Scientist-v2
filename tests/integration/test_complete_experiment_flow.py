import pytest
import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient
from ulid import ULID
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

@pytest.fixture(scope="session")
def mongodb_url():
    url = os.environ.get('MONGODB_URL')
    if not url:
        pytest.skip("MONGODB_URL not set - run with real MongoDB for integration tests")
    return url

@pytest.fixture
def test_db(mongodb_url):
    client = MongoClient(mongodb_url)
    db = client['ai-scientist-test-integration']
    
    yield db
    
    client.drop_database('ai-scientist-test-integration')
    client.close()

@pytest.fixture
def temp_exp_dir():
    tmpdir = tempfile.mkdtemp(prefix="test_exp_")
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)

class TestCompleteExperimentFlow:
    """Test the complete experiment flow from QUEUED to COMPLETED."""
    
    def test_hypothesis_to_run_creation(self, test_db):
        """Test creating hypothesis and queuing a run."""
        hypothesis_id = str(ULID())
        run_id = str(ULID())
        
        hypothesis = {
            "_id": hypothesis_id,
            "title": "Test Crystal LLMs",
            "idea": "A test hypothesis",
            "ideaJson": {
                "Name": "test_crystal_llms",
                "Title": "Test Crystal LLMs",
                "Short Hypothesis": "Test hypothesis",
                "Abstract": "Testing the system",
                "Experiments": ["Test experiment 1"],
                "Risk Factors and Limitations": ["Test limitation"]
            },
            "createdAt": datetime.utcnow(),
            "createdBy": "test"
        }
        
        test_db['hypotheses'].insert_one(hypothesis)
        
        run = {
            "_id": run_id,
            "hypothesisId": hypothesis_id,
            "status": "QUEUED",
            "claimedBy": None,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }
        
        test_db['runs'].insert_one(run)
        
        created_run = test_db['runs'].find_one({"_id": run_id})
        assert created_run is not None
        assert created_run["status"] == "QUEUED"
        assert created_run["hypothesisId"] == hypothesis_id
    
    def test_run_claim_and_status_transitions(self, test_db):
        """Test run transitions through all states."""
        run_id = str(ULID())
        hypothesis_id = str(ULID())
        
        test_db['hypotheses'].insert_one({
            "_id": hypothesis_id,
            "title": "Test",
            "idea": "Test",
            "ideaJson": {},
            "createdAt": datetime.utcnow(),
            "createdBy": "test"
        })
        
        run = {
            "_id": run_id,
            "hypothesisId": hypothesis_id,
            "status": "QUEUED",
            "claimedBy": None,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }
        
        test_db['runs'].insert_one(run)
        
        # QUEUED -> SCHEDULED
        test_db['runs'].update_one(
            {"_id": run_id},
            {"$set": {"status": "SCHEDULED", "claimedBy": "test-pod"}}
        )
        
        run = test_db['runs'].find_one({"_id": run_id})
        assert run["status"] == "SCHEDULED"
        assert run["claimedBy"] == "test-pod"
        
        # SCHEDULED -> RUNNING
        test_db['runs'].update_one(
            {"_id": run_id},
            {"$set": {"status": "RUNNING", "startedAt": datetime.utcnow()}}
        )
        
        run = test_db['runs'].find_one({"_id": run_id})
        assert run["status"] == "RUNNING"
        assert run["startedAt"] is not None
        
        # RUNNING -> COMPLETED
        test_db['runs'].update_one(
            {"_id": run_id},
            {"$set": {"status": "COMPLETED", "completedAt": datetime.utcnow()}}
        )
        
        run = test_db['runs'].find_one({"_id": run_id})
        assert run["status"] == "COMPLETED"
        assert run["completedAt"] is not None
    
    def test_event_sequence_tracking(self, test_db):
        """Test that event sequences are tracked correctly."""
        run_id = str(ULID())
        
        test_db['runs'].insert_one({
            "_id": run_id,
            "hypothesisId": str(ULID()),
            "status": "RUNNING",
            "lastEventSeq": 0,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        })
        
        for seq in range(1, 6):
            event = {
                "_id": str(ULID()),
                "runId": run_id,
                "type": "ai.run.log",
                "data": {"message": f"Event {seq}", "level": "info"},
                "source": "test",
                "timestamp": datetime.utcnow(),
                "seq": seq
            }
            
            test_db['events'].insert_one(event)
            test_db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"lastEventSeq": seq}}
            )
        
        run = test_db['runs'].find_one({"_id": run_id})
        assert run["lastEventSeq"] == 5
        
        events = list(test_db['events'].find({"runId": run_id}).sort("seq", 1))
        assert len(events) == 5
        assert [e["seq"] for e in events] == [1, 2, 3, 4, 5]
    
    def test_stage_progress_updates(self, test_db):
        """Test stage progress tracking with detailed metrics."""
        run_id = str(ULID())
        
        test_db['runs'].insert_one({
            "_id": run_id,
            "hypothesisId": str(ULID()),
            "status": "RUNNING",
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        })
        
        # Simulate progress updates
        for iteration in range(1, 5):
            test_db['runs'].update_one(
                {"_id": run_id},
                {"$set": {
                    "currentStage": {
                        "name": "Stage_1",
                        "progress": iteration / 14.0,
                        "iteration": iteration,
                        "maxIterations": 14,
                        "goodNodes": iteration,
                        "buggyNodes": iteration - 1,
                        "totalNodes": iteration * 2 - 1
                    }
                }}
            )
        
        run = test_db['runs'].find_one({"_id": run_id})
        stage = run["currentStage"]
        
        assert stage["name"] == "Stage_1"
        assert stage["iteration"] == 4
        assert stage["goodNodes"] == 4
        assert stage["buggyNodes"] == 3
        assert stage["totalNodes"] == 7
    
    def test_stage_timing_accumulation(self, test_db):
        """Test that stage timing is tracked correctly."""
        run_id = str(ULID())
        
        test_db['runs'].insert_one({
            "_id": run_id,
            "hypothesisId": str(ULID()),
            "status": "RUNNING",
            "stageTiming": {},
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        })
        
        stages = ["Stage_1", "Stage_2", "Stage_3", "Stage_4"]
        durations = [1200, 800, 1500, 900]
        
        for stage, duration in zip(stages, durations):
            test_db['runs'].update_one(
                {"_id": run_id},
                {"$set": {
                    f"stageTiming.{stage}.elapsed_s": duration,
                    f"stageTiming.{stage}.duration_s": duration
                }}
            )
        
        run = test_db['runs'].find_one({"_id": run_id})
        timing = run["stageTiming"]
        
        assert timing["Stage_1"]["duration_s"] == 1200
        assert timing["Stage_4"]["duration_s"] == 900
        assert len(timing) == 4
    
    def test_error_recording(self, test_db):
        """Test that errors are properly recorded."""
        run_id = str(ULID())
        
        test_db['runs'].insert_one({
            "_id": run_id,
            "hypothesisId": str(ULID()),
            "status": "RUNNING",
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        })
        
        # Simulate error
        error_info = {
            "status": "FAILED",
            "failedAt": datetime.utcnow(),
            "errorType": "AuthenticationError",
            "errorMessage": "Invalid API key",
            "retryCount": 0
        }
        
        test_db['runs'].update_one(
            {"_id": run_id},
            {"$set": error_info}
        )
        
        run = test_db['runs'].find_one({"_id": run_id})
        
        assert run["status"] == "FAILED"
        assert run["errorType"] == "AuthenticationError"
        assert "API key" in run["errorMessage"]
        assert run["retryCount"] == 0

class TestArtifactTracking:
    def test_artifact_registration(self, test_db):
        """Test artifact registration in database."""
        run_id = str(ULID())
        artifact_id = str(ULID())
        
        artifact = {
            "_id": artifact_id,
            "runId": run_id,
            "key": f"runs/{run_id}/plot.png",
            "uri": f"runs/{run_id}/plot.png",
            "contentType": "image/png",
            "size": 12345,
            "createdAt": datetime.utcnow()
        }
        
        test_db['artifacts'].insert_one(artifact)
        
        artifacts = list(test_db['artifacts'].find({"runId": run_id}))
        assert len(artifacts) == 1
        assert artifacts[0]["contentType"] == "image/png"
        assert artifacts[0]["size"] == 12345

class TestExperimentMonitor:
    def test_monitor_detects_new_plots(self, temp_exp_dir):
        """Test that monitor detects new plot files."""
        from experiment_monitor import ExperimentMonitor
        
        events_emitted = []
        
        def mock_emit(event_type, data):
            events_emitted.append((event_type, data))
        
        monitor = ExperimentMonitor(str(temp_exp_dir), "test-run", mock_emit)
        
        # Create a plot file
        plots_dir = temp_exp_dir / "plots"
        plots_dir.mkdir()
        plot_file = plots_dir / "test_plot.png"
        plot_file.write_bytes(b"fake png data")
        
        # Scan for updates
        monitor.scan_for_updates()
        
        # Check that artifact was detected
        artifact_events = [e for e in events_emitted if e[0] == "ai.artifact.detected"]
        assert len(artifact_events) > 0
        assert "test_plot.png" in str(artifact_events[0][1])
    
    def test_monitor_streams_log_files(self, temp_exp_dir):
        """Test that monitor streams log files."""
        from experiment_monitor import ExperimentMonitor
        
        events_emitted = []
        
        def mock_emit(event_type, data):
            events_emitted.append((event_type, data))
        
        monitor = ExperimentMonitor(str(temp_exp_dir), "test-run", mock_emit)
        
        # Create a log file
        logs_dir = temp_exp_dir / "logs"
        logs_dir.mkdir()
        log_file = logs_dir / "experiment.log"
        log_file.write_text("Test log line 1\nTest log line 2\nERROR: Something failed\n")
        
        # Scan twice to ensure incremental reading works
        monitor.scan_for_updates()
        initial_count = len([e for e in events_emitted if e[0] == "ai.run.log"])
        
        # Append more logs
        with open(log_file, 'a') as f:
            f.write("Another log line\n")
        
        monitor.scan_for_updates()
        final_count = len([e for e in events_emitted if e[0] == "ai.run.log"])
        
        assert final_count > initial_count
        
        # Check error level detection
        error_logs = [e for e in events_emitted if e[0] == "ai.run.log" and e[1].get("level") == "error"]
        assert len(error_logs) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=long"])

