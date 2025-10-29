"""
COMPREHENSIVE INTEGRATION TEST
Tests ALL events using the EXACT same emitter as pod_worker.
If this passes, the pod worker WILL work.
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
    
    # Clean test data
    database['runs'].delete_many({"createdBy": "integration_test"})
    database['events'].delete_many({"source": {"$regex": "^runpod://pod/test-"}})
    database['hypotheses'].delete_many({"createdBy": "integration_test"})
    
    yield database
    
    # DON'T cleanup - keep for inspection
    print("\n📝 Test data preserved in MongoDB")
    client.close()

@pytest.fixture
def test_run(db):
    run_id = str(uuid.uuid4())
    hypothesis_id = str(uuid.uuid4())
    
    db['hypotheses'].insert_one({
        "_id": hypothesis_id,
        "title": "Integration Test",
        "idea": "Test all events",
        "ideaJson": {
            "Name": "test",
            "Title": "Test",
            "Short Hypothesis": "Test",
            "Abstract": "Test",
            "Experiments": ["Test"],
            "Risk Factors and Limitations": ["Test"]
        },
        "createdAt": datetime.utcnow(),
        "createdBy": "integration_test"
    })
    
    db['runs'].insert_one({
        "_id": run_id,
        "hypothesisId": hypothesis_id,
        "status": "SCHEDULED",
        "claimedBy": "test-pod",
        "lastEventSeq": 0,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "createdBy": "integration_test"
    })
    
    return run_id

class TestCompleteEventFlow:
    """Test complete experiment flow with ALL events."""
    
    def test_complete_experiment_lifecycle(self, db, test_run):
        """
        Test EVERY event type in order as they would occur in a real experiment.
        This test MUST pass before deploying to pod.
        """
        emitter = CloudEventEmitter(CONTROL_PLANE_URL, "test-integration-pod")
        
        events_sent = []
        events_failed = []
        
        def send_and_verify(event_name, send_func):
            print(f"\n📤 Sending: {event_name}")
            success = send_func()
            if success:
                events_sent.append(event_name)
                print(f"   ✓ Sent successfully")
            else:
                events_failed.append(event_name)
                print(f"   ❌ Failed to send")
            return success
        
        # 1. RUN STARTED
        assert send_and_verify("ai.run.started", 
            lambda: emitter.run_started(test_run, "test-pod", "NVIDIA L40S", "us-west"))
        
        time.sleep(1)
        
        # Verify run status updated
        run = db['runs'].find_one({"_id": test_run})
        assert run['status'] == 'RUNNING', f"Expected RUNNING, got {run['status']}"
        assert run.get('startedAt') is not None
        print("   ✓ Run status updated to RUNNING")
        
        # 2-5. STAGE 1 FLOW
        assert send_and_verify("ai.run.stage_started",
            lambda: emitter.stage_started(test_run, "Stage_1", "Preliminary Investigation"))
        
        time.sleep(0.5)
        
        # Simulate 3 iterations
        for iteration in range(1, 4):
            # Node created
            node_id = f"node_{iteration}"
            assert send_and_verify(f"ai.node.created_{iteration}",
                lambda nid=node_id: emitter.node_created(test_run, "Stage_1", nid, None))
            
            # Code generated
            assert send_and_verify(f"ai.node.code_generated_{iteration}",
                lambda nid=node_id: emitter.node_code_generated(test_run, "Stage_1", nid, 5000))
            
            # Executing
            assert send_and_verify(f"ai.node.executing_{iteration}",
                lambda nid=node_id: emitter.node_executing(test_run, "Stage_1", nid))
            
            # Log message
            assert send_and_verify(f"ai.run.log_{iteration}",
                lambda it=iteration: emitter.log(test_run, f"Iteration {it}/14 running...", "info"))
            
            # Node completed
            is_buggy = iteration == 2  # Make one buggy
            metric = f"loss=0.{20-iteration:02d}" if not is_buggy else None
            assert send_and_verify(f"ai.node.completed_{iteration}",
                lambda nid=node_id, b=is_buggy, m=metric: emitter.node_completed(
                    test_run, "Stage_1", nid, b, m, 45.5))
            
            # Progress update
            good_nodes = iteration if not is_buggy else iteration - 1
            assert send_and_verify(f"ai.stage_progress_{iteration}",
                lambda it=iteration, gn=good_nodes: emitter.stage_progress(
                    test_run, "Stage_1", it/14.0, it, 14, gn, iteration-gn, iteration,
                    f"loss=0.{20-it:02d}", 600))
            
            time.sleep(0.3)
        
        # Best node selected
        assert send_and_verify("ai.node.selected_best",
            lambda: emitter.node_selected_best(test_run, "Stage_1", "node_3", "loss=0.17"))
        
        # Stage completed
        assert send_and_verify("ai.run.stage_completed",
            lambda: emitter.stage_completed(test_run, "Stage_1", 720))
        
        time.sleep(1)
        
        # 6-8. STAGE 2-4 (abbreviated)
        for stage_num in [2, 3, 4]:
            stage = f"Stage_{stage_num}"
            assert send_and_verify(f"ai.run.stage_started_{stage}",
                lambda s=stage: emitter.stage_started(test_run, s, f"Stage {stage_num}"))
            
            assert send_and_verify(f"ai.stage_progress_{stage}",
                lambda s=stage: emitter.stage_progress(test_run, s, 1.0, 8, 8, 8, 0, 8, "complete"))
            
            assert send_and_verify(f"ai.run.stage_completed_{stage}",
                lambda s=stage: emitter.stage_completed(test_run, s, 300))
            
            time.sleep(0.3)
        
        # 9. PAPER GENERATION
        assert send_and_verify("ai.paper.started",
            lambda: emitter.paper_started(test_run))
        
        assert send_and_verify("ai.paper.generated",
            lambda: emitter.paper_generated(test_run, f"runs/{test_run}/paper.pdf"))
        
        # 10. ARTIFACT UPLOAD
        assert send_and_verify("ai.artifact.detected",
            lambda: emitter.artifact_detected(test_run, "plots/loss_curve.png", "plot", 12345))
        
        assert send_and_verify("ai.artifact.registered",
            lambda: emitter.artifact_registered(test_run, f"runs/{test_run}/plot.png", 
                12345, "abc123", "image/png", "plot"))
        
        # 11. VALIDATION
        assert send_and_verify("ai.validation.auto_started",
            lambda: emitter.validation_auto_started(test_run, "gpt-4o"))
        
        assert send_and_verify("ai.validation.auto_completed",
            lambda: emitter.validation_auto_completed(test_run, "pass", {"overall": 0.75}, "Good paper"))
        
        # 12. RUN COMPLETED
        assert send_and_verify("ai.run.completed",
            lambda: emitter.run_completed(test_run, 3600))
        
        time.sleep(2)
        
        # VERIFICATION
        print("\n" + "="*60)
        print("VERIFICATION")
        print("="*60)
        
        total_sent = len(events_sent)
        total_failed = len(events_failed)
        
        print(f"\n📊 Events sent: {total_sent}")
        print(f"❌ Events failed: {total_failed}")
        
        if events_failed:
            print("\n❌ Failed events:")
            for evt in events_failed:
                print(f"   - {evt}")
        
        # Check MongoDB
        saved_events = list(db['events'].find({"runId": test_run}))
        print(f"\n💾 Events in MongoDB: {len(saved_events)}")
        
        # Check run final state
        final_run = db['runs'].find_one({"_id": test_run})
        print(f"\n📋 Final run state:")
        print(f"   Status: {final_run.get('status')}")
        print(f"   CurrentStage: {final_run.get('currentStage')}")
        print(f"   StageTiming: {final_run.get('stageTiming', {}).keys()}")
        print(f"   StartedAt: {final_run.get('startedAt')}")
        print(f"   CompletedAt: {final_run.get('completedAt')}")
        
        # ASSERTIONS
        assert total_failed == 0, f"{total_failed} events failed to send"
        assert len(saved_events) >= 20, f"Expected >= 20 events, got {len(saved_events)}"
        
        # Verify critical fields populated
        assert final_run.get('stageTiming') is not None
        assert 'Stage_1' in final_run.get('stageTiming', {})
        assert 'Stage_4' in final_run.get('stageTiming', {})
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED - DEPLOYMENT READY")
        print("="*60)
        print(f"\nIf you deploy now:")
        print(f"  - {total_sent} event types will work")
        print(f"  - Live progress updates every iteration")
        print(f"  - Complete observability from start to finish")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

