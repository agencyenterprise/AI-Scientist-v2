# Comprehensive Testing Plan for AI Scientist v2

**Goal**: Sleep-at-night confidence that deployments won't break critical functionality.

## 🎯 Test Coverage Areas

### 1. Event System (Critical Path)
### 2. Artifact System (File uploads/downloads)
### 3. Pod Worker Pipeline (Experiment execution)
### 4. API/Backend (Event processing, state management)
### 5. UI/Frontend (Real-time updates, user interactions)
### 6. End-to-End (Full experiment lifecycle)

---

## 📋 Testing Pyramid

```
                    E2E Tests (5%)
                 Integration Tests (25%)
              Unit Tests (70%)
```

---

## 1️⃣ Unit Tests (Fast, Isolated, Many)

### 1.1 Pod Worker Unit Tests (`tests/unit/test_pod_worker.py`)

**Event Emission:**
- ✅ Test each event type is formatted correctly
- ✅ Test event sequencing (seq numbers increment)
- ✅ Test event batching and flushing
- ✅ Test CloudEvent envelope structure
- ✅ Test event deduplication

```python
# tests/unit/test_pod_worker_events.py
def test_run_started_event_format():
    """Ensure run_started events have correct structure"""
    
def test_stage_progress_event_has_required_fields():
    """Ensure stage_progress includes iteration, goodNodes, etc"""
    
def test_event_sequence_increments():
    """Verify EVENT_SEQ increments on each emit"""
    
def test_event_batching_flushes_at_threshold():
    """Verify batch emits when reaching 50 events"""
```

**Artifact Upload:**
- ✅ Test presigned URL generation
- ✅ Test file hashing (SHA256)
- ✅ Test content-type detection
- ✅ Test artifact registration event
- ✅ Test upload retry logic

**Stage Context Manager:**
- ✅ Test stage_started emission on __enter__
- ✅ Test stage_completed emission on successful __exit__
- ✅ Test exception handling (no premature failure events)
- ✅ Test stage timing calculation

**Error Handling:**
- ✅ Test top-level exception catching
- ✅ Test run_failed event emission
- ✅ Test error type classification (retryable vs non-retryable)
- ✅ Test signal handlers (SIGINT, SIGTERM)

### 1.2 Backend Unit Tests (`orchestrator/apps/web/lib/__tests__/`)

**Event Validation:**
- ✅ Test CloudEvents schema validation
- ✅ Test each event data schema (30+ event types)
- ✅ Test unrecognized keys rejection
- ✅ Test required field validation

```typescript
// lib/__tests__/cloudevents.test.ts
describe('Event Schema Validation', () => {
  it('validates ai.run.stage_progress with all fields')
  it('rejects ai.run.stage_progress with invalid progress value')
  it('validates ai.artifact.registered with required fields')
  it('rejects events with extra unrecognized keys')
})
```

**State Machine:**
- ✅ Test valid status transitions (QUEUED → RUNNING → COMPLETED)
- ✅ Test invalid transitions are blocked (COMPLETED → RUNNING)
- ✅ Test status transition logging

**Repository Layer:**
- ✅ Test run CRUD operations
- ✅ Test stage CRUD operations
- ✅ Test artifact registration
- ✅ Test event storage with deduplication

### 1.3 Frontend Unit Tests (`orchestrator/apps/web/__tests__/components/`)

**Component Tests:**
- ✅ Test RunDetailClient renders stages correctly
- ✅ Test StageProgress shows progress bars
- ✅ Test ArtifactList displays artifacts
- ✅ Test status badges (RUNNING, COMPLETED, FAILED)
- ✅ Test real-time update hooks

---

## 2️⃣ Integration Tests (Realistic, Database Involved)

### 2.1 Event Processing Integration (`tests/integration/test_event_processing.py`)

**Event Ingestion Flow:**
```python
def test_complete_event_flow():
    """
    1. POST event to /api/ingest/event
    2. Verify event stored in events collection
    3. Verify run/stage updated correctly
    4. Verify state transitions applied
    """
    
def test_out_of_order_event_rejection():
    """
    1. Send event with seq=5
    2. Send event with seq=3
    3. Verify seq=3 rejected (out of order)
    """
    
def test_duplicate_event_deduplication():
    """
    1. Send same event ID twice
    2. Verify second is marked duplicate
    3. Verify only one stored in DB
    """
```

**Event Type Coverage:**
- ✅ Test ai.run.started → updates status to RUNNING
- ✅ Test ai.run.stage_started → creates stage record
- ✅ Test ai.run.stage_progress → updates stage progress
- ✅ Test ai.run.stage_completed → marks stage complete
- ✅ Test ai.run.failed → transitions to FAILED status
- ✅ Test ai.artifact.registered → creates artifact record
- ✅ Test ai.validation.auto_completed → creates validation

### 2.2 Artifact System Integration (`tests/integration/test_artifacts.py`)

**Artifact Upload Flow:**
```python
def test_artifact_upload_flow():
    """
    1. Request presigned PUT URL
    2. Upload file to MinIO
    3. Send artifact.registered event
    4. Verify artifact accessible via GET URL
    """
    
def test_artifact_download_flow():
    """
    1. Upload artifact
    2. Request presigned GET URL
    3. Download and verify SHA256 matches
    """
```

### 2.3 MongoDB State Management (`tests/integration/test_mongodb_state.py`)

**Database Consistency:**
```python
def test_run_stage_consistency():
    """Verify run.currentStage matches stages collection"""
    
def test_event_seq_monotonic():
    """Verify lastEventSeq always increases"""
    
def test_concurrent_updates():
    """Verify multiple workers don't corrupt state"""
```

---

## 3️⃣ Contract Tests (Schema Compatibility)

### 3.1 Event Contract Tests (`tests/contracts/test_event_contracts.py`)

**Purpose**: Ensure pod worker and API agree on event schemas.

```python
def test_pod_emits_valid_run_started():
    """Pod's run_started event matches API schema"""
    event = pod_worker.emit_run_started_example()
    assert validates_against_schema(event, RunStartedDataZ)

def test_all_event_types_have_matching_schemas():
    """For each event pod can emit, API has a schema"""
    pod_events = get_all_pod_event_types()
    api_schemas = EVENT_TYPE_DATA_SCHEMAS.keys()
    assert set(pod_events) == set(api_schemas)
```

**Contract Testing Tool**: Use Pact or OpenAPI schemas to enforce contracts.

### 3.2 Database Schema Contracts (`tests/contracts/test_db_schemas.py`)

```python
def test_run_schema_compatibility():
    """Verify Run schema accepts all fields pod writes"""
    
def test_stage_schema_compatibility():
    """Verify Stage schema accepts all fields pod writes"""
```

---

## 4️⃣ End-to-End Tests (Slow, Full System)

### 4.1 Full Experiment Lifecycle (`tests/e2e/test_full_experiment.py`)

**Happy Path:**
```python
@pytest.mark.e2e
@pytest.mark.slow
def test_complete_experiment_lifecycle():
    """
    1. Create hypothesis via UI
    2. Queue run
    3. Pod worker claims run
    4. Stage_1 executes
    5. Stage_2 executes  
    6. Stage_3 generates paper
    7. Stage_4 validates
    8. Run completes
    9. Artifacts uploaded
    10. UI shows COMPLETED status
    """
    # This test takes 30-60 minutes!
```

**Failure Recovery:**
```python
@pytest.mark.e2e
def test_experiment_failure_recovery():
    """
    1. Start experiment
    2. Simulate crash in Stage_2
    3. Verify status goes to FAILED
    4. Verify error message captured
    5. Verify partial results saved
    """
```

### 4.2 UI Real-Time Updates (`tests/e2e/test_ui_realtime.py`)

**Using Playwright:**
```typescript
test('UI updates in real-time as experiment progresses', async ({ page }) => {
  await page.goto(`/runs/${runId}`)
  
  // Verify initial state
  await expect(page.locator('[data-testid="status"]')).toHaveText('RUNNING')
  
  // Trigger stage completion event
  await emitEvent('ai.run.stage_completed', { stage: 'Stage_1' })
  
  // Verify UI updates (with SSE or polling)
  await expect(page.locator('[data-testid="stage-1"]')).toHaveText('COMPLETED')
})
```

---

## 5️⃣ Performance/Load Tests

### 5.1 Event Throughput (`tests/performance/test_event_throughput.py`)

```python
def test_api_handles_1000_events_per_second():
    """Simulate high-volume event ingestion"""
    events = generate_random_events(10000)
    start = time.time()
    
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(post_event, events)
    
    duration = time.time() - start
    assert duration < 10  # 1000+ events/sec
```

### 5.2 Concurrent Experiments (`tests/performance/test_concurrent_runs.py`)

```python
def test_10_concurrent_experiments():
    """Verify system handles multiple runs without corruption"""
    # Start 10 runs simultaneously
    # Verify events don't mix between runs
    # Verify all complete successfully
```

---

## 6️⃣ Chaos/Resilience Tests

### 6.1 Network Failures (`tests/chaos/test_network_failures.py`)

```python
def test_pod_retries_failed_event_emission():
    """Pod should retry event emission on network failure"""
    
def test_artifact_upload_retries_on_timeout():
    """Artifact upload should retry on timeout"""
```

### 6.2 Database Failures (`tests/chaos/test_db_failures.py`)

```python
def test_event_processing_retries_on_db_timeout():
    """API should retry DB operations on timeout"""
    
def test_graceful_degradation_when_mongodb_slow():
    """System should degrade gracefully, not crash"""
```

---

## 🛠️ Testing Infrastructure

### Test Fixtures & Factories

```python
# tests/fixtures/run_factory.py
def create_test_run(**overrides):
    """Factory for creating test runs"""
    return {
        "_id": str(uuid4()),
        "hypothesisId": str(uuid4()),
        "status": "QUEUED",
        "createdAt": datetime.utcnow(),
        **overrides
    }

# tests/fixtures/event_factory.py
def create_cloudevent(event_type, data, **overrides):
    """Factory for creating CloudEvents"""
    return {
        "specversion": "1.0",
        "id": str(ULID()),
        "source": "test",
        "type": event_type,
        "subject": f"run/{data['run_id']}",
        "time": datetime.utcnow().isoformat() + "Z",
        "datacontenttype": "application/json",
        "data": data,
        **overrides
    }
```

### Test Databases

```python
# tests/conftest.py
@pytest.fixture
def test_db():
    """Isolated test database (MongoDB)"""
    client = MongoClient(MONGODB_TEST_URL)
    db = client['ai-scientist-test']
    
    yield db
    
    # Cleanup
    client.drop_database('ai-scientist-test')
```

### Mock Services

```python
# tests/mocks/minio_mock.py
class MockMinIOClient:
    """Mock MinIO for testing artifact uploads"""
    def __init__(self):
        self.uploads = {}
    
    def put_object(self, bucket, key, data):
        self.uploads[key] = data
```

---

## 📊 Test Execution Strategy

### CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - name: Unit Tests (Python)
        run: pytest tests/unit/ -v --cov
      
      - name: Unit Tests (TypeScript)
        run: npm run test:unit
  
  integration-tests:
    runs-on: ubuntu-latest
    services:
      mongodb:
        image: mongo:7
      minio:
        image: minio/minio
    steps:
      - name: Integration Tests
        run: pytest tests/integration/ -v
  
  e2e-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - name: E2E Tests (Critical Path Only)
        run: pytest tests/e2e/ -v -m "critical"
```

### Pre-Commit Hooks

```bash
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: unit-tests
        name: Run unit tests
        entry: pytest tests/unit/ -x
        language: system
        pass_filenames: false
```

---

## 🎯 Test Coverage Goals

| Area | Target Coverage | Priority |
|------|----------------|----------|
| Pod Worker Event Emission | 95% | 🔴 Critical |
| Event Ingestion (API) | 95% | 🔴 Critical |
| State Machine Transitions | 100% | 🔴 Critical |
| Artifact Upload/Download | 90% | 🟡 High |
| UI Components | 70% | 🟢 Medium |
| Experiment Pipeline | 60% | 🟢 Medium |

---

## 🚀 Implementation Phases

### Phase 1: Critical Path (Week 1-2)
- ✅ Unit tests for all event types
- ✅ Integration tests for event ingestion
- ✅ Contract tests for event schemas
- ✅ Basic artifact upload/download tests

**Deliverable**: 80% confidence in event system

### Phase 2: Full Coverage (Week 3-4)
- ✅ State machine exhaustive testing
- ✅ Error handling and recovery tests
- ✅ Performance baseline tests
- ✅ UI component tests

**Deliverable**: 90% confidence in deployments

### Phase 3: Advanced Testing (Week 5-6)
- ✅ E2E critical path tests
- ✅ Chaos/resilience tests
- ✅ Load testing
- ✅ Monitoring and alerting integration

**Deliverable**: Sleep-at-night confidence

---

## 🔧 Tools & Libraries

### Python Testing
- **pytest**: Test runner
- **pytest-cov**: Coverage reporting
- **pytest-mock**: Mocking
- **pytest-asyncio**: Async test support
- **faker**: Test data generation
- **freezegun**: Time mocking
- **responses**: HTTP mocking

### TypeScript/JavaScript Testing
- **Vitest**: Test runner (faster than Jest)
- **Testing Library**: React component testing
- **MSW**: API mocking
- **Playwright**: E2E browser testing

### Infrastructure Testing
- **testcontainers**: Docker containers for tests
- **moto**: AWS/S3 mocking (if not using MinIO)

---

## 📈 Monitoring Test Health

### Test Metrics Dashboard
- ✅ Test execution time trends
- ✅ Flaky test detection
- ✅ Coverage trends over time
- ✅ Failure rate by test suite

### Automated Test Reporting
```python
# Generate HTML report after tests
pytest --html=report.html --self-contained-html

# Upload to S3 or artifact storage
# Link in PR comments
```

---

## 🎓 Testing Best Practices

1. **Fast Feedback Loop**: Unit tests run in < 5 seconds
2. **Isolated Tests**: No test depends on another
3. **Deterministic**: Same input = same output (no flakiness)
4. **Readable**: Test names explain what they verify
5. **Maintainable**: Use factories and fixtures, not copy-paste
6. **Realistic**: Integration tests use real databases (in containers)
7. **Comprehensive**: Cover happy path, edge cases, and errors

---

## 🚨 Red Flags to Test For

Based on current issues:

1. ✅ **Premature failure events** (FIXED: removed from StageContext)
2. ✅ **Schema validation mismatches** (pod writes fields API doesn't accept)
3. ✅ **Event order violations** (out-of-sequence events)
4. ✅ **State transition violations** (COMPLETED → RUNNING)
5. ✅ **Race conditions** (concurrent updates)
6. ✅ **Artifact upload failures** (presigned URL expiration)
7. ✅ **Heartbeat timeouts** (pod appears dead when it's not)

---

## 📝 Example: Critical Path Test

```python
# tests/integration/test_critical_path.py

@pytest.mark.integration
def test_critical_event_flow(test_db, api_client):
    """
    The most critical test: Verify a run progresses correctly
    through its lifecycle with proper event handling.
    """
    # Setup
    run_id = str(uuid4())
    hypothesis_id = str(uuid4())
    
    # Create hypothesis
    hypothesis = create_test_hypothesis(hypothesis_id)
    test_db['hypotheses'].insert_one(hypothesis)
    
    # Create run
    run = create_test_run(run_id, hypothesis_id, status="QUEUED")
    test_db['runs'].insert_one(run)
    
    # 1. Pod claims run and starts
    event = create_cloudevent("ai.run.started", {
        "run_id": run_id,
        "pod_id": "test-pod",
        "gpu": "A100",
        "region": "us-west"
    })
    response = api_client.post("/api/ingest/event", json=event)
    assert response.status_code == 201
    
    # Verify status changed
    run = test_db['runs'].find_one({"_id": run_id})
    assert run['status'] == "RUNNING"
    assert run['pod']['id'] == "test-pod"
    
    # 2. Stage 1 starts
    event = create_cloudevent("ai.run.stage_started", {
        "run_id": run_id,
        "stage": "Stage_1",
        "desc": "Preliminary Investigation"
    })
    response = api_client.post("/api/ingest/event", json=event)
    assert response.status_code == 201
    
    # Verify stage created
    stage = test_db['stages'].find_one({"runId": run_id, "name": "Stage_1"})
    assert stage is not None
    assert stage['status'] == "RUNNING"
    
    # 3. Stage 1 progress
    event = create_cloudevent("ai.run.stage_progress", {
        "run_id": run_id,
        "stage": "Stage_1",
        "progress": 0.5,
        "iteration": 5,
        "max_iterations": 10,
        "good_nodes": 3,
        "buggy_nodes": 2,
        "total_nodes": 5
    })
    response = api_client.post("/api/ingest/event", json=event)
    assert response.status_code == 201
    
    # Verify progress updated
    stage = test_db['stages'].find_one({"runId": run_id, "name": "Stage_1"})
    assert stage['progress'] == 0.5
    run = test_db['runs'].find_one({"_id": run_id})
    assert run['currentStage']['progress'] == 0.5
    assert run['currentStage']['goodNodes'] == 3
    
    # 4. Artifact uploaded
    event = create_cloudevent("ai.artifact.registered", {
        "run_id": run_id,
        "key": f"runs/{run_id}/plot.png",
        "bytes": 1024,
        "sha256": "abc123",
        "content_type": "image/png",
        "kind": "plot"
    })
    response = api_client.post("/api/ingest/event", json=event)
    assert response.status_code == 201
    
    # Verify artifact registered
    artifacts = list(test_db['artifacts'].find({"runId": run_id}))
    assert len(artifacts) == 1
    assert artifacts[0]['kind'] == "plot"
    
    # 5. Stage 1 completes
    event = create_cloudevent("ai.run.stage_completed", {
        "run_id": run_id,
        "stage": "Stage_1",
        "duration_s": 300
    })
    response = api_client.post("/api/ingest/event", json=event)
    assert response.status_code == 201
    
    # Verify stage completed
    stage = test_db['stages'].find_one({"runId": run_id, "name": "Stage_1"})
    assert stage['status'] == "COMPLETED"
    assert stage['progress'] == 1.0
    
    # 6. Run completes
    event = create_cloudevent("ai.run.completed", {
        "run_id": run_id,
        "total_duration_s": 1200
    })
    response = api_client.post("/api/ingest/event", json=event)
    assert response.status_code == 201
    
    # Verify run completed
    run = test_db['runs'].find_one({"_id": run_id})
    assert run['status'] == "COMPLETED"
    assert run['completedAt'] is not None
    
    print("✅ Critical path test PASSED")
```

---

## 🎉 Success Criteria

**You can sleep at night when:**

1. ✅ 95%+ of critical paths have automated tests
2. ✅ CI runs full test suite on every PR (< 10 min)
3. ✅ Integration tests catch 90%+ of bugs before production
4. ✅ Test failures are clear and actionable
5. ✅ No flaky tests (< 1% failure rate on passing code)
6. ✅ Coverage reports show gaps, not just percentages
7. ✅ Production incidents trigger new tests (learn from failures)

---

## 📚 Next Steps

1. **Review this plan** - adjust priorities based on your needs
2. **Start with Phase 1** - critical path tests first
3. **Set up CI/CD** - automate test execution
4. **Write one test per day** - build the suite incrementally
5. **Monitor test health** - keep tests fast and reliable
6. **Celebrate wins** - every bug caught by tests is a win!

---

**Remember**: Tests are an investment. The goal isn't 100% coverage—it's confidence to deploy frequently without fear.

