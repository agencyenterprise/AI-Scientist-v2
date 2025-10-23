# Observability System - Current Status & Next Steps

## What's Actually Working ✅

### Backend (Pod Worker)
- ✅ Pod worker loads `.env` automatically
- ✅ No auto-retry (max_retries = 0)
- ✅ Errors saved to database (errorType, errorMessage, failedAt)
- ✅ Folder reuse on retry
- ✅ Status transitions work (QUEUED → SCHEDULED → RUNNING → FAILED/COMPLETED)

### Frontend (UI)
- ✅ ErrorDisplay component renders
- ✅ Run status badge works
- ✅ Basic metadata displays (pod ID, GPU, timestamps)
- ✅ StageProgressPanel component built (not receiving data yet)
- ✅ StageTimingView component built (not receiving data yet)
- ✅ LiveLogViewer component built (not receiving data yet)
- ✅ PlotGallery component built (not receiving data yet)

### Database
- ✅ Enhanced Run schema with all fields
- ✅ Events saved to events collection
- ✅ Runs have currentStage, stageTiming fields

## What's NOT Working ❌

### Critical Issues

1. **Event Emission from Experiment Code**
   - ❌ `perform_experiments_bfts` receives `event_callback` parameter
   - ❌ BUT doesn't pass it to `manager.run()`
   - ❌ So `step_callback` emits events but they fail validation
   - ❌ Result: No progress events reach frontend

2. **Event Schema Mismatch**
   - ❌ Events being emitted don't match CloudEvents schema
   - ❌ Getting 422 Unprocessable Entity
   - ❌ Likely missing required fields or wrong format

3. **Monitor Thread**
   - ✅ Starts in background
   - ❌ Not properly scanning files (no events from it)
   - ❌ Integration not tested

4. **Live Data Flow**
   - ❌ No events → No data in DB → Frontend shows nothing
   - ❌ Even though experiment IS running

## What Needs to be Fixed (Priority Order)

### P0: Core Event Flow (Blocking Everything)

1. **Fix `manager.run()` to accept callback**
   - File: `ai_scientist/treesearch/agent_manager.py`
   - Line: ~703
   - Need to pass `step_callback` and have it call event_callback
   - Estimate: 30 minutes

2. **Fix Event Schema Validation**
   - Current events don't match CloudEventsEnvelopeZ
   - Need to debug what fields are missing/wrong
   - Check: `orchestrator/apps/web/lib/schemas/cloudevents.ts`
   - Estimate: 20 minutes

3. **Test Event Round-Trip**
   - Emit test event from pod
   - Verify it's saved to MongoDB
   - Verify frontend can fetch and display it
   - Estimate: 15 minutes

### P1: Monitor Integration

4. **Fix ExperimentMonitor**
   - Currently starts but doesn't emit
   - Need to verify file scanning works
   - Add logging to debug what it's seeing
   - Estimate: 20 minutes

5. **Test Artifact Upload**
   - Create test plot file
   - Verify monitor detects it
   - Verify it uploads to MinIO
   - Verify artifact appears in UI
   - Estimate: 15 minutes

### P2: Frontend Components

6. **Wire Up Components**
   - Components are built but need data
   - Once events flow, they should "just work"
   - May need minor tweaks
   - Estimate: 10 minutes

## Recommended Approach

### Option A: Quick Win (2-3 hours)
Focus ONLY on basic status + error display:
- Skip live progress/metrics/logs
- Just show: Status, Error message, Stage name
- This already mostly works!

### Option B: Complete System (8-12 hours)
Fix everything properly:
1. Event emission from experiments
2. Schema validation
3. Monitor integration
4. Full frontend with all components
5. Comprehensive testing

### Option C: Hybrid (4-6 hours)
Core observability only:
- Status updates ✓
- Error messages ✓
- Stage progress (iteration count, timing)
- Basic logs
- Skip: metrics, plots, detailed node info

## My Honest Recommendation

**Start with Option C (Hybrid)**

Benefits:
- Manageable scope
- Clear success criteria
- Actually testable in reasonable time
- Covers 80% of your needs

Then later, if needed, add:
- Detailed metrics
- Progressive plots
- Node-level debugging

## Next Session Plan

If you want to continue:

1. **Session 1 (2 hours)**: Fix event emission + schema validation
2. **Session 2 (2 hours)**: Get basic progress/timing working
3. **Session 3 (1 hour)**: Test end-to-end, fix bugs
4. **Session 4 (1 hour)**: Polish and document

## How to Stop Current Experiment

**On pod:**
```bash
# Kill pod worker (stops claiming new experiments)
pkill -f pod_worker.py

# The current experiment will continue in background
# To stop it completely:
pkill -f python
```

**Clean database:**
```bash
# Use the script I created
python << 'EOF'
from pymongo import MongoClient
import os
client = MongoClient(os.environ.get("MONGODB_URL"))
db = client['ai-scientist']
db['runs'].delete_many({'status': {'$in': ['QUEUED', 'SCHEDULED', 'RUNNING']}})
db['hypotheses'].delete_many({})
db['events'].delete_many({})
print("✓ Cleaned up")
EOF
```

---

**I apologize for overpromising.** The pieces are there but the integration isn't complete. 

**What do you want to do?** Take a break? Continue with realistic scope? Or document and come back later?

