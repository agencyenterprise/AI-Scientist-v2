# Testing Plan - Event-Driven Infrastructure

## 🎯 Testing Strategy

We use a **layered testing approach** with increasing levels of integration:

1. **Unit Tests** - Individual functions and modules
2. **Integration Tests** - API endpoints with mocked dependencies
3. **End-to-End Tests** - Full pipeline on staging environment
4. **Production Smoke Tests** - Verify deployment health

## 📋 Test Coverage

### ✅ Unit Tests (TypeScript/Vitest)

**Location:** `orchestrator/apps/web/lib/**/*.test.ts`

#### CloudEvents Validation (`lib/schemas/cloudevents.test.ts`)
- ✅ Valid CloudEvents envelope accepted
- ✅ Invalid specversion rejected
- ✅ Missing required fields rejected
- ✅ Invalid ISO 8601 timestamps rejected
- ✅ Extensions validation (seq must be positive)
- ✅ Event data validation for all 16 event types
- ✅ Stage names validated (Stage_1 - Stage_4 only)
- ✅ Progress values must be 0.0-1.0
- ✅ Verdict values must be pass/fail
- ✅ Unknown event types rejected

#### Event Processing (`lib/services/events.service.test.ts`)
- ✅ Events create database records
- ✅ `lastEventSeq` updated after processing
- ✅ Out-of-order events ignored (seq ≤ lastEventSeq)
- ✅ Duplicate events ignored (same ID)
- ✅ Stage events create/update stages
- ✅ Validation events create validation records
- ✅ Artifact events create artifact records
- ✅ State transitions validated (illegal transitions rejected)

**Run unit tests:**
```bash
cd orchestrator/apps/web
npm test
```

### 🔗 Integration Tests (API Endpoints)

**Location:** `test_event_ingestion.py`

#### Single Event Endpoint (`POST /api/ingest/event`)
- ✅ Valid CloudEvents JSON accepted (201 Created)
- ✅ Invalid envelope rejected (422 Unprocessable Entity)
- ✅ Duplicate events return success with "duplicate" status
- ✅ Response includes event_id

#### Batch Event Endpoint (`POST /api/ingest/events`)
- ✅ Valid NDJSON batch accepted (202 Accepted)
- ✅ Partial success handled (207 Multi-Status)
- ✅ Invalid lines rejected, valid lines processed
- ✅ Response includes `accepted`, `duplicates`, `invalid` counts
- ✅ Error details include line numbers

#### Event Deduplication
- ✅ Duplicate event IDs ignored
- ✅ Events_seen collection tracks processed events
- ✅ TTL index removes old events (7 days)

**Run integration tests:**
```bash
# Make sure backend is running
python test_event_ingestion.py
```

Expected output:
```
✅ Single event test PASSED
✅ Batch event test PASSED
✅ Duplicate detection test PASSED
✅ Invalid event rejection test PASSED
```

### 🤖 Pod Worker Tests (Python)

**What to Test:**

1. **Atomic Queue Fetch**
   - Only ONE pod claims each run
   - `claimedBy` field set correctly
   - No duplicate claims (race condition test)

2. **Event Emission**
   - Events generated with valid ULID IDs
   - Sequence numbers increment correctly
   - Batch flushing works (50 events/batch)
   - Network failures handled gracefully

3. **Global Exception Handler**
   - Unhandled exceptions emit `ai.run.failed` events
   - Traceback included in event data
   - `retryable` flag set correctly

4. **Stage Context Manager**
   - Stage start/complete events emitted
   - Exceptions auto-reported with stage context
   - Duration tracked

5. **Pipeline Integration**
   - Ideation runs when `ideaJson` missing
   - All 4 stages execute
   - Artifacts uploaded to MinIO
   - Auto-validation completes

**Manual Testing (Required):**

Since the pod worker interacts with real systems (MongoDB, MinIO, LLMs), we need **manual testing on RunPod**:

```bash
# On RunPod instance
cd AI-Scientist-v2

# 1. Test atomic fetch (run 2 workers simultaneously)
./start_worker.sh &
./start_worker.sh &
# Check logs - should see different runs claimed

# 2. Test error handling (force error)
# Modify hypothesis to have invalid JSON
# Check frontend shows error with traceback

# 3. Test full pipeline
# Create hypothesis via frontend
# Watch worker logs
# Verify frontend updates in real-time
```

### 🌐 End-to-End Tests

**Scenario 1: Happy Path**

1. **Setup:**
   - Backend deployed on Railway
   - RunPod worker running
   - MongoDB + MinIO accessible

2. **Steps:**
   ```bash
   # Via frontend
   1. Create hypothesis: "Test Compositional Regularization"
   2. System creates run with status QUEUED
   3. Worker claims run (status → SCHEDULED → RUNNING)
   4. Worker runs ideation (if needed)
   5. Worker runs 4 stages
   6. Worker generates paper PDF
   7. Worker runs auto-validation
   8. Status → AWAITING_HUMAN
   ```

3. **Verify:**
   - ✅ Frontend shows all stage progress
   - ✅ Paper PDF downloadable
   - ✅ Events logged in database
   - ✅ No errors in worker logs
   - ✅ Total time: 70-140 minutes

**Scenario 2: Error Recovery**

1. **Force OOM Error:**
   - Create hypothesis with huge dataset
   - Verify `ai.run.failed` event emitted
   - Verify frontend shows error with code="OOMError"
   - Verify traceback visible

2. **Force Network Timeout:**
   - Disconnect network briefly during stage
   - Verify retry logic works
   - Verify run completes after reconnection

3. **Worker Crash:**
   - Kill worker mid-run (Ctrl+C)
   - Restart worker
   - Verify run stays in RUNNING (claimedBy still set)
   - **Manual intervention:** Reset run to QUEUED
   - Verify new worker picks it up

**Scenario 3: Concurrency**

1. **Multiple Pods:**
   - Start 3 RunPod workers
   - Create 10 hypotheses
   - Verify each run claimed by exactly ONE worker
   - Verify no duplicate claims (check `claimedBy` field)
   - Verify all runs complete successfully

2. **Event Ordering:**
   - Check MongoDB `events` collection
   - Verify `seq` numbers are monotonic per run
   - Verify no gaps in sequence (except if worker crashed)

### 🔒 Security Tests

**Not Implemented Yet** (MVP has no auth):

- [ ] API key authentication
- [ ] Request signature validation
- [ ] Rate limiting
- [ ] IP allowlisting

**For Now:**
- Rely on private network (Railway ↔ RunPod trusted)
- Frontend authentication already implemented
- MongoDB credentials secured via env vars

### 📊 Performance Tests

**Baseline Targets:**

| Metric | Target | Measured |
|--------|--------|----------|
| Event ingestion (single) | < 100ms | TBD |
| Event ingestion (batch 50) | < 200ms | TBD |
| MongoDB query (queue fetch) | < 50ms | TBD |
| Worker polling interval | 10s | ✅ |
| Events per run | 100-200 | TBD |
| Run duration | 70-140 min | TBD |

**Load Test Scenarios:**

1. **High Event Volume:**
   ```bash
   # Send 1000 events in 1 second
   for i in {1..20}; do
     python test_event_ingestion.py &
   done
   ```
   Expected: All events processed, no duplicates

2. **Many Concurrent Runs:**
   - Create 50 hypotheses
   - Start 5 workers
   - Verify all complete within expected time
   - Check MongoDB/MinIO for resource usage

## 🎓 Testing Checklist

### Pre-Deployment

- [ ] Run unit tests: `cd orchestrator/apps/web && npm test`
- [ ] Run integration tests: `python test_event_ingestion.py`
- [ ] Run linter: `npm run lint`
- [ ] Run type check: `npm run typecheck`
- [ ] Check no linter errors on new files

### Post-Deployment (Staging)

- [ ] Health check: `curl https://your-app.railway.app/api/health`
- [ ] Test single event: `python test_event_ingestion.py`
- [ ] Create test hypothesis via frontend
- [ ] Verify worker picks it up
- [ ] Verify frontend shows updates
- [ ] Verify paper generated and downloadable

### Production Validation

- [ ] Smoke test: Create simple hypothesis
- [ ] Monitor worker logs for errors
- [ ] Check MongoDB event counts
- [ ] Verify artifact uploads to MinIO
- [ ] Test error case (invalid hypothesis)
- [ ] Verify error shown in frontend

## 🐛 Known Limitations

1. **No WebSocket Support**
   - Frontend polls MongoDB (acceptable for MVP)
   - Consider adding WebSockets later for sub-second updates

2. **No Authentication on Ingest Endpoints**
   - Trusts all incoming events (private network only)
   - Add API keys before making public

3. **No Automatic Retry Logic**
   - Failed runs stay in FAILED status
   - Manual reset required: `python manage_runs.py reset <run_id>`
   - Consider adding auto-retry for `retryable: true` errors

4. **No Distributed Tracing**
   - `traceparent` field optional but not used
   - Consider integrating OpenTelemetry later

5. **No Heartbeat Monitoring**
   - Runs can get stuck if worker crashes without emitting `failed` event
   - Consider adding timeout detection (e.g., no events for 30 minutes)

## 📈 Test Metrics

**Code Coverage Target:** 70% (pragmatic, not aiming for 100%)

**Critical Paths (Must Have High Coverage):**
- ✅ Event validation (100% - all event types)
- ✅ Event processing (90% - core state transitions)
- ✅ Deduplication (100% - prevents data corruption)
- ⚠️ Pod worker (50% - mostly manual testing)

**Non-Critical (Lower Coverage OK):**
- Frontend components (visual, best tested manually)
- CLI tools (`manage_runs.py` - utility, not production)
- Documentation (no tests needed)

## 🚀 Running Tests

### Quick Test Suite (Before Push)

```bash
# Backend unit tests
cd orchestrator/apps/web
npm test

# Backend linter
npm run lint

# Integration tests (requires backend running)
cd ../../../
python test_event_ingestion.py
```

**Expected time:** ~30 seconds

### Full Test Suite (Before Deploy)

```bash
# 1. Unit tests
cd orchestrator/apps/web
npm test
npm run typecheck
npm run lint

# 2. Integration tests
cd ../../../
python test_event_ingestion.py

# 3. Manual E2E test (staging)
# - Create hypothesis via frontend
# - Watch worker logs
# - Verify completion

# 4. Check logs
python manage_runs.py stats
python manage_runs.py list --limit 5
```

**Expected time:** ~5 minutes + 1 experiment duration

## 📝 Test Maintenance

**When to Update Tests:**

1. **New Event Type Added:**
   - Add validation schema to `cloudevents.ts`
   - Add test case to `cloudevents.test.ts`
   - Add handler to `events.service.ts`
   - Add test case to `events.service.test.ts`

2. **State Machine Changed:**
   - Update `runStateMachine.ts`
   - Add test for new transitions
   - Update `events.service.ts` handlers

3. **New MongoDB Collection:**
   - Add repo file
   - Add schema file
   - Add tests for CRUD operations

4. **Breaking API Change:**
   - Update `test_event_ingestion.py`
   - Update OpenAPI docs (if we add them)
   - Notify pod worker maintainers

## 🎯 Definition of Done

A feature is **"done"** when:

1. ✅ Unit tests written and passing
2. ✅ Integration tests updated (if applicable)
3. ✅ Linter passes
4. ✅ TypeScript type check passes
5. ✅ Manual E2E test on staging
6. ✅ Documentation updated
7. ✅ No linter errors introduced

## 🔮 Future Test Improvements

1. **Automated E2E Tests:**
   - Use Playwright to test full UI flow
   - Mock LLM responses for faster tests
   - Run on every PR

2. **Load Testing:**
   - Set up k6 or Locust
   - Test 100+ concurrent runs
   - Measure MongoDB/MinIO limits

3. **Chaos Engineering:**
   - Randomly kill workers
   - Drop network packets
   - Verify system recovers

4. **CI/CD Integration:**
   - Run tests on every push
   - Block merge if tests fail
   - Auto-deploy on green build

5. **Monitoring & Alerts:**
   - Add Datadog/Sentry
   - Alert on high error rates
   - Track P95/P99 latencies

---

**Next Steps:** Run the test suite and fix any issues before deploying to production!

