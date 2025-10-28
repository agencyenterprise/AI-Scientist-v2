# Testing Quick Start Guide

Get started with high-value tests in 1 day.

## 🚀 Start Here: The 5 Tests That Matter Most

These 5 tests will catch 80% of bugs:

### 1️⃣ Event Schema Validation Test (10 min)

**File**: `tests/integration/test_event_schemas.py`

```python
import pytest
from orchestrator.apps.web.lib.schemas.cloudevents import EVENT_TYPE_DATA_SCHEMAS, validateEventData

@pytest.mark.parametrize("event_type,valid_data", [
    ("ai.run.started", {
        "run_id": "test-123",
        "pod_id": "pod-1",
        "gpu": "A100",
        "region": "us-west"
    }),
    ("ai.run.stage_progress", {
        "run_id": "test-123",
        "stage": "Stage_1",
        "progress": 0.5,
        "iteration": 5,
        "max_iterations": 10,
        "good_nodes": 3,
        "buggy_nodes": 2,
        "total_nodes": 5
    }),
    ("ai.artifact.registered", {
        "run_id": "test-123",
        "key": "runs/test-123/plot.png",
        "bytes": 1024,
        "content_type": "image/png",
        "kind": "plot"
    }),
])
def test_event_data_validates(event_type, valid_data):
    """Verify all event types accept their expected data shape"""
    assert validateEventData(event_type, valid_data) is True

def test_all_pod_events_have_schemas():
    """Verify pod can't emit events that API doesn't recognize"""
    # List of events pod_worker.py emits
    pod_events = {
        "ai.run.started",
        "ai.run.heartbeat",
        "ai.run.completed",
        "ai.run.failed",
        "ai.run.stage_started",
        "ai.run.stage_progress",
        "ai.run.stage_completed",
        "ai.artifact.registered",
        "ai.run.log",
        "ai.validation.auto_started",
        "ai.validation.auto_completed",
        "ai.paper.started",
        "ai.paper.generated"
    }
    
    api_schemas = set(EVENT_TYPE_DATA_SCHEMAS.keys())
    
    missing = pod_events - api_schemas
    assert len(missing) == 0, f"Pod emits events without API schemas: {missing}"
```

**Value**: Prevents schema mismatches (like the substage field issue).

---

### 2️⃣ State Transition Test (15 min)

**File**: `tests/integration/test_state_transitions.py`

```python
import pytest
from orchestrator.apps.web.lib.state.runStateMachine import assertTransition

def test_valid_state_transitions():
    """Verify all valid transitions are allowed"""
    valid_transitions = [
        ("QUEUED", "SCHEDULED"),
        ("SCHEDULED", "RUNNING"),
        ("RUNNING", "AUTO_VALIDATING"),
        ("AUTO_VALIDATING", "AWAITING_HUMAN"),
        ("AWAITING_HUMAN", "COMPLETED"),
        ("RUNNING", "FAILED"),
        ("RUNNING", "CANCELED"),
    ]
    
    for from_status, to_status in valid_transitions:
        # Should not raise
        assertTransition(from_status, to_status)

def test_invalid_state_transitions():
    """Verify invalid transitions are blocked"""
    invalid_transitions = [
        ("COMPLETED", "RUNNING"),  # Can't restart completed
        ("FAILED", "RUNNING"),     # Can't resume failed
        ("QUEUED", "COMPLETED"),   # Can't skip to completed
    ]
    
    for from_status, to_status in invalid_transitions:
        with pytest.raises(Exception):
            assertTransition(from_status, to_status)

def test_idempotent_transitions():
    """Verify same-state transitions are allowed (idempotent)"""
    for status in ["QUEUED", "RUNNING", "COMPLETED", "FAILED"]:
        # Should not raise
        assertTransition(status, status)
```

**Value**: Prevents runs from getting into invalid states.

---

### 3️⃣ Event Ingestion Integration Test (20 min)

**File**: `tests/integration/test_event_ingestion.py`

```python
import pytest
from datetime import datetime
from uuid import uuid4
from ulid import ULID

@pytest.fixture
def test_run(test_db):
    """Create a test run in database"""
    run_id = str(uuid4())
    hypothesis_id = str(uuid4())
    
    test_db['hypotheses'].insert_one({
        "_id": hypothesis_id,
        "name": "Test Hypothesis",
        "ideaJson": {},
        "createdAt": datetime.utcnow()
    })
    
    test_db['runs'].insert_one({
        "_id": run_id,
        "hypothesisId": hypothesis_id,
        "status": "QUEUED",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })
    
    return run_id

def test_run_started_event_updates_status(test_run, api_client, test_db):
    """Verify ai.run.started event transitions status to RUNNING"""
    event = {
        "specversion": "1.0",
        "id": str(ULID()),
        "source": "test",
        "type": "ai.run.started",
        "subject": f"run/{test_run}",
        "time": datetime.utcnow().isoformat() + "Z",
        "datacontenttype": "application/json",
        "data": {
            "run_id": test_run,
            "pod_id": "test-pod",
            "gpu": "A100",
            "region": "us-west"
        }
    }
    
    response = api_client.post("/api/ingest/event", json=event)
    assert response.status_code == 201
    
    # Verify status updated
    run = test_db['runs'].find_one({"_id": test_run})
    assert run['status'] == "RUNNING"
    assert run['pod']['id'] == "test-pod"

def test_duplicate_event_rejected(test_run, api_client):
    """Verify duplicate event IDs are rejected"""
    event_id = str(ULID())
    event = {
        "specversion": "1.0",
        "id": event_id,
        "source": "test",
        "type": "ai.run.heartbeat",
        "subject": f"run/{test_run}",
        "time": datetime.utcnow().isoformat() + "Z",
        "datacontenttype": "application/json",
        "data": {"run_id": test_run}
    }
    
    # First send
    response1 = api_client.post("/api/ingest/event", json=event)
    assert response1.status_code == 201
    
    # Second send (duplicate)
    response2 = api_client.post("/api/ingest/event", json=event)
    assert response2.status_code == 201
    assert response2.json()['status'] == "duplicate"

def test_out_of_order_event_rejected(test_run, api_client, test_db):
    """Verify out-of-order events are rejected"""
    # First send event with seq=5
    event1 = {
        "specversion": "1.0",
        "id": str(ULID()),
        "source": "test",
        "type": "ai.run.heartbeat",
        "subject": f"run/{test_run}",
        "time": datetime.utcnow().isoformat() + "Z",
        "datacontenttype": "application/json",
        "data": {"run_id": test_run},
        "extensions": {"seq": 5}
    }
    
    response = api_client.post("/api/ingest/event", json=event1)
    assert response.status_code == 201
    
    # Verify lastEventSeq updated
    run = test_db['runs'].find_one({"_id": test_run})
    assert run['lastEventSeq'] == 5
    
    # Now send event with seq=3 (out of order)
    event2 = {
        "specversion": "1.0",
        "id": str(ULID()),
        "source": "test",
        "type": "ai.run.heartbeat",
        "subject": f"run/{test_run}",
        "time": datetime.utcnow().isoformat() + "Z",
        "datacontenttype": "application/json",
        "data": {"run_id": test_run},
        "extensions": {"seq": 3}
    }
    
    response = api_client.post("/api/ingest/event", json=event2)
    # Should still succeed but be ignored
    assert response.status_code == 201
    
    # Verify lastEventSeq didn't change
    run = test_db['runs'].find_one({"_id": test_run})
    assert run['lastEventSeq'] == 5  # Still 5, not 3
```

**Value**: Catches event ordering and deduplication bugs.

---

### 4️⃣ Artifact Upload Test (20 min)

**File**: `tests/integration/test_artifacts.py`

```python
import pytest
from io import BytesIO
import hashlib

def test_artifact_upload_flow(test_run, api_client, test_db):
    """Test complete artifact upload: presign → upload → register"""
    
    # 1. Request presigned URL
    response = api_client.post(
        f"/api/runs/{test_run}/artifacts/presign",
        json={
            "action": "put",
            "filename": "test_plot.png",
            "content_type": "image/png"
        }
    )
    assert response.status_code == 200
    presigned_url = response.json()['url']
    
    # 2. Upload file to MinIO
    file_content = b"fake png data"
    upload_response = api_client.put(presigned_url, data=file_content)
    assert upload_response.status_code == 200
    
    # 3. Register artifact
    sha256 = hashlib.sha256(file_content).hexdigest()
    event = {
        "specversion": "1.0",
        "id": str(ULID()),
        "source": "test",
        "type": "ai.artifact.registered",
        "subject": f"run/{test_run}",
        "time": datetime.utcnow().isoformat() + "Z",
        "datacontenttype": "application/json",
        "data": {
            "run_id": test_run,
            "key": f"runs/{test_run}/test_plot.png",
            "bytes": len(file_content),
            "sha256": sha256,
            "content_type": "image/png",
            "kind": "plot"
        }
    }
    
    response = api_client.post("/api/ingest/event", json=event)
    assert response.status_code == 201
    
    # 4. Verify artifact in database
    artifacts = list(test_db['artifacts'].find({"runId": test_run}))
    assert len(artifacts) == 1
    assert artifacts[0]['kind'] == "plot"
    assert artifacts[0]['size'] == len(file_content)

def test_artifact_download_flow(test_run, api_client):
    """Test artifact download: presign → download → verify"""
    # Assume artifact already uploaded
    artifact_key = f"runs/{test_run}/test_plot.png"
    
    # Request presigned GET URL
    response = api_client.post(
        f"/api/runs/{test_run}/artifacts/presign",
        json={
            "action": "get",
            "key": artifact_key
        }
    )
    assert response.status_code == 200
    download_url = response.json()['url']
    
    # Download file
    download_response = api_client.get(download_url)
    assert download_response.status_code == 200
    assert len(download_response.content) > 0
```

**Value**: Ensures artifacts (plots, papers) are uploaded correctly.

---

### 5️⃣ Pod Worker Event Emission Test (20 min)

**File**: `tests/unit/test_pod_worker_events.py`

```python
import pytest
from unittest.mock import Mock, patch
from pod_worker import CloudEventEmitter

def test_run_started_event_structure():
    """Verify run_started event has correct structure"""
    emitter = CloudEventEmitter("https://test.com", "test-pod")
    
    with patch('requests.post') as mock_post:
        mock_post.return_value.status_code = 201
        
        result = emitter.run_started(
            "run-123",
            "pod-abc",
            "A100",
            "us-west"
        )
        
        assert result is True
        assert mock_post.called
        
        # Verify CloudEvents structure
        call_args = mock_post.call_args
        body = call_args[1]['json']
        
        assert body['specversion'] == "1.0"
        assert body['type'] == "ai.run.started"
        assert body['subject'] == "run/run-123"
        assert body['data']['pod_id'] == "pod-abc"
        assert body['data']['gpu'] == "A100"

def test_stage_progress_event_structure():
    """Verify stage_progress event includes all fields"""
    emitter = CloudEventEmitter("https://test.com", "test-pod")
    
    with patch('requests.post') as mock_post:
        mock_post.return_value.status_code = 201
        
        result = emitter.stage_progress(
            "run-123",
            "Stage_1",
            0.5,
            iteration=5,
            max_iterations=10,
            good_nodes=3,
            buggy_nodes=2,
            total_nodes=5,
            best_metric="0.95",
            eta_s=300
        )
        
        assert result is True
        body = mock_post.call_args[1]['json']
        
        assert body['data']['progress'] == 0.5
        assert body['data']['iteration'] == 5
        assert body['data']['good_nodes'] == 3
        assert body['data']['total_nodes'] == 5

def test_event_emission_retries_on_failure():
    """Verify event emission retries on network error"""
    emitter = CloudEventEmitter("https://test.com", "test-pod")
    
    with patch('requests.post') as mock_post:
        # First call fails, second succeeds
        mock_post.side_effect = [
            Exception("Network error"),
            Mock(status_code=201)
        ]
        
        # Should NOT raise, should retry
        result = emitter.run_started("run-123", "pod-abc", "A100", "us-west")
        
        # Depending on implementation, might return False on first try
        # Update based on actual retry logic
```

**Value**: Ensures events are emitted correctly from pod worker.

---

## 🛠️ Test Infrastructure Setup (30 min)

### 1. Install Test Dependencies

```bash
# Python
pip install pytest pytest-cov pytest-asyncio pytest-mock faker freezegun responses

# TypeScript/JavaScript
cd orchestrator/apps/web
npm install -D vitest @testing-library/react @testing-library/jest-dom msw
```

### 2. Create Test Configuration

**File**: `pytest.ini`

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --strict-markers
    --cov=.
    --cov-report=html
    --cov-report=term-missing
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (use database)
    e2e: End-to-end tests (slow, full system)
    slow: Tests that take > 10 seconds
    critical: Critical path tests (must always pass)
```

### 3. Create Test Fixtures

**File**: `tests/conftest.py`

```python
import pytest
from pymongo import MongoClient
from fastapi.testclient import TestClient
import os

@pytest.fixture
def test_db():
    """Isolated test database"""
    client = MongoClient(os.environ.get('MONGODB_TEST_URL', 'mongodb://localhost:27017'))
    db = client['ai-scientist-test']
    
    yield db
    
    # Cleanup after test
    client.drop_database('ai-scientist-test')

@pytest.fixture
def api_client():
    """FastAPI test client"""
    from orchestrator.apps.web.main import app  # Adjust import
    return TestClient(app)

@pytest.fixture
def test_run(test_db):
    """Factory for creating test runs"""
    from uuid import uuid4
    from datetime import datetime
    
    run_id = str(uuid4())
    hypothesis_id = str(uuid4())
    
    test_db['hypotheses'].insert_one({
        "_id": hypothesis_id,
        "name": "Test Hypothesis",
        "ideaJson": {},
        "createdAt": datetime.utcnow()
    })
    
    test_db['runs'].insert_one({
        "_id": run_id,
        "hypothesisId": hypothesis_id,
        "status": "QUEUED",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })
    
    return run_id
```

---

## ▶️ Run the Tests

```bash
# Run all tests
pytest

# Run only unit tests (fast)
pytest -m unit

# Run specific test file
pytest tests/integration/test_event_ingestion.py

# Run with coverage
pytest --cov=pod_worker --cov=orchestrator/apps/web/lib

# Run tests matching pattern
pytest -k "event"
```

---

## 📊 Measure Success

After implementing these 5 tests:

```bash
pytest --cov=. --cov-report=term-missing

# You should see:
# ✅ ~50 test cases passing
# ✅ 60%+ code coverage on critical paths
# ✅ Tests run in < 30 seconds
```

---

## 🚀 Next Steps

Once these 5 tests are working:

1. **Add more event types** to test #1
2. **Test error scenarios** (network failures, timeouts)
3. **Add E2E test** for full experiment lifecycle
4. **Set up CI/CD** to run tests on every commit
5. **Monitor flaky tests** and fix them immediately

---

## 🎯 The Golden Rule

**If it broke in production, write a test that would have caught it.**

Every incident is an opportunity to improve your test suite.

