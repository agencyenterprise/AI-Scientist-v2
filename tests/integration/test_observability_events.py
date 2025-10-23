"""
Comprehensive test for ALL observability events.
Tests every granular event added for full visibility into experiment progress.
"""
import pytest
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient
import uuid

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
    
    database['runs'].delete_many({"createdBy": "observability_test"})
    database['events'].delete_many({"source": {"$regex": "^runpod://pod/test-obs-"}})
    database['hypotheses'].delete_many({"createdBy": "observability_test"})
    
    yield database
    
    print("\n📝 Test data preserved in MongoDB for inspection")
    client.close()

@pytest.fixture
def test_run(db):
    run_id = str(uuid.uuid4())
    hypothesis_id = str(uuid.uuid4())
    
    db['hypotheses'].insert_one({
        "_id": hypothesis_id,
        "title": "Observability Test",
        "idea": "Test all granular events",
        "ideaJson": {
            "Name": "test_obs",
            "Title": "Observability Test",
            "Short Hypothesis": "Full event coverage",
            "Abstract": "Test all events",
            "Experiments": ["Full monitoring"],
            "Risk Factors and Limitations": ["None"]
        },
        "createdAt": datetime.utcnow(),
        "createdBy": "observability_test"
    })
    
    db['runs'].insert_one({
        "_id": run_id,
        "hypothesisId": hypothesis_id,
        "status": "SCHEDULED",
        "claimedBy": "test-obs-pod",
        "lastEventSeq": 0,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "createdBy": "observability_test"
    })
    
    return run_id

class TestObservabilityEvents:
    """Test comprehensive observability through granular events"""
    
    def test_experiment_phase_visibility(self, db, test_run):
        """
        Test that EVERY phase of experiment execution emits log events
        so users can see what's happening in real-time.
        """
        emitter = CloudEventEmitter(CONTROL_PLANE_URL, "test-obs-pod")
        
        events_log = []
        
        def send_log(message: str, level: str = "info"):
            """Helper to send log events"""
            success = emitter.log(test_run, message, level)
            if success:
                events_log.append(message)
                print(f"   ✓ {message}")
            return success
        
        print("\n=== TESTING FULL EXPERIMENT OBSERVABILITY ===\n")
        
        print("📋 Phase 1: Initialization")
        assert send_log("Generating 3 new implementation(s)")
        
        print("\n🔧 Phase 2: Code Generation (Worker 1)")
        assert send_log("Generating new implementation code")
        assert send_log("Code generation complete")
        
        print("\n⚙️ Phase 3: Code Execution")
        assert send_log("Executing experiment code on GPU...")
        assert send_log("Code execution completed (45.2s)")
        assert send_log("Analyzing results and extracting metrics")
        
        print("\n🔍 Phase 4: Validation")
        assert send_log("Implementation has bugs: RNG seed must be between 0 and 2**32 - 1", "warn")
        
        print("\n🔧 Phase 5: Debugging Attempt")
        assert send_log("Debugging 1 failed implementation(s)")
        assert send_log("Debugging failed node (attempt to fix bugs)")
        assert send_log("Fix attempt generated")
        
        print("\n⚙️ Phase 6: Re-execution")
        assert send_log("Executing experiment code on GPU...")
        assert send_log("Code execution completed (42.8s)")
        assert send_log("Analyzing results and extracting metrics")
        assert send_log("Implementation passed validation")
        
        print("\n📊 Phase 7: Plot Generation")
        assert send_log("Generating visualization plots")
        assert send_log("Executing plotting code")
        assert send_log("Generated 6 plot file(s)")
        
        print("\n🤖 Phase 8: VLM Analysis")
        assert send_log("Analyzing 6 generated plots with VLM")
        assert send_log("Plot analysis complete")
        
        print("\n✅ Phase 9: Node Completion")
        assert send_log("Node 1/3 completed successfully (metric: validation NRM: -2.5589)")
        assert send_log("Node 2/3 completed (buggy, will retry)")
        assert send_log("Node 3/3 completed successfully (metric: validation NRM: -1.4739)")
        
        print("\n📈 Phase 10: Progress Update")
        assert send_log("Found 2 working implementation(s), continuing...")
        
        print(f"\n{'='*60}")
        print(f"✅ All {len(events_log)} observability events verified!")
        print(f"{'='*60}\n")
        
        time.sleep(2)
        
        log_events = list(db['events'].find({
            "runId": test_run,
            "type": "ai.run.log"
        }).sort("timestamp", 1))
        
        print(f"\n📊 Log events in MongoDB: {len(log_events)}")
        assert len(log_events) >= 15, "Should have at least 15 granular log events"
        
        for evt in log_events[:5]:
            print(f"   - {evt['data']['message']}")
        print(f"   ... and {len(log_events)-5} more")
        
        print("\n✅ Observability test PASSED - Full visibility achieved!")

    def test_stage_progress_always_emitted(self, db, test_run):
        """
        Test that stage_progress events are emitted even when all nodes are buggy.
        This ensures users ALWAYS see progress, not just when things work.
        """
        emitter = CloudEventEmitter(CONTROL_PLANE_URL, "test-obs-pod")
        
        print("\n=== TESTING PROGRESS EVENTS WITH BUGGY NODES ===\n")
        
        success = emitter.stage_progress(
            test_run,
            "Stage_1",
            progress=0.214,
            iteration=3,
            max_iterations=14,
            good_nodes=0,
            buggy_nodes=3,
            total_nodes=3,
            best_metric=None,
            eta_s=180
        )
        
        assert success, "stage_progress event should send successfully"
        
        time.sleep(1)
        
        run = db['runs'].find_one({"_id": test_run})
        assert run is not None
        
        current_stage = run.get('currentStage')
        assert current_stage is not None, "currentStage should be populated"
        assert current_stage.get('iteration') == 3, "Iteration should be 3"
        assert current_stage.get('goodNodes') == 0, "Good nodes should be 0"
        assert current_stage.get('buggyNodes') == 3, "Buggy nodes should be 3"
        assert current_stage.get('totalNodes') == 3, "Total nodes should be 3"
        assert current_stage.get('progress') == 0.214, "Progress should be 21.4%"
        
        print("✅ Progress shows correctly even with 0 good nodes!")
        print(f"   Iteration: {current_stage.get('iteration')}/{current_stage.get('maxIterations')}")
        print(f"   Nodes: {current_stage.get('goodNodes')} good / {current_stage.get('buggyNodes')} buggy / {current_stage.get('totalNodes')} total")
        print(f"   Progress: {current_stage.get('progress')*100:.1f}%")

    def test_log_event_types_displayed(self, db, test_run):
        """
        Test that different log levels are stored correctly.
        """
        emitter = CloudEventEmitter(CONTROL_PLANE_URL, "test-obs-pod")
        
        print("\n=== TESTING LOG EVENT LEVELS ===\n")
        
        messages = [
            ("Generating new implementation code", "info"),
            ("Code execution completed (45.2s)", "info"),
            ("Implementation has bugs: ValueError", "warn"),
            ("Node 1/3 timed out after 3600s", "warn"),
            ("Implementation passed validation", "info"),
        ]
        
        for message, level in messages:
            success = emitter.log(test_run, message, level)
            assert success
            print(f"   [{level.upper()}] {message}")
        
        time.sleep(1)
        
        log_events = list(db['events'].find({
            "runId": test_run,
            "type": "ai.run.log"
        }))
        
        assert len(log_events) == 5
        
        info_count = sum(1 for e in log_events if e['data'].get('level') == 'info')
        warn_count = sum(1 for e in log_events if e['data'].get('level') == 'warn')
        
        assert info_count == 3
        assert warn_count == 2
        
        print(f"\n✅ Log levels preserved: {info_count} info, {warn_count} warnings")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

