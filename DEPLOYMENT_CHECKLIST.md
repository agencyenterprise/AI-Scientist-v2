# Deployment Checklist - Complete Observability System

## Pre-Deployment Validation

### Local Machine

```bash
cd /Users/jessica/AEStudio/agi/AI-Scientist-v2

# 1. Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# 2. Run pre-deployment test
source .venv/bin/activate
python test_observability.py

# Expected output: ✅ ALL TESTS PASSED
```

If tests fail, fix issues before proceeding.

### Frontend (Railway)

```bash
cd orchestrator/apps/web

# 1. Install dependencies
pnpm install

# 2. Type check
pnpm typecheck

# 3. Build
pnpm build

# Expected: No errors
```

## Deployment to Pod

### Step 1: Update Code

```bash
# On pod
cd "/workspace/AI-Scientist-v2 copy"

# Pull latest
git pull origin feat/additions

# Verify critical files updated
ls -lh pod_worker.py monitor_experiment.py
```

### Step 2: Verify Environment

```bash
# Check .env exists
cat .env

# Should contain:
# - OPENAI_API_KEY=sk-proj-...
# - MONGODB_URL=mongodb+srv://...
# - CONTROL_PLANE_URL=https://...

# If missing, create it now
```

### Step 3: Clean Up Old Processes

```bash
# Kill everything
pkill -f python

# Verify nothing running
ps aux | grep python
```

### Step 4: Start Worker

```bash
# Start with clean state
python pod_worker.py

# Expected output:
# ============================================================
# 🤖 AI Scientist Pod Worker
# ============================================================
# Pod ID: ...
# Control Plane: https://...
# ============================================================
#
# ✓ Connected to MongoDB
#
# 🔍 Polling for experiments...
```

## Create Test Run

### Step 1: Create Hypothesis

Frontend → Hypotheses → Create:
- **Title**: `Test Observability System`
- **Idea**: `A simple test to validate that all observability features work correctly`

### Step 2: Watch Run Page

Click "View" on the new run. You should see **immediately**:

#### Within 10 seconds:
- ✅ Status: QUEUED → SCHEDULED → RUNNING
- ✅ Pod ID and instance type

#### Within 30 seconds:
- ✅ Stage 1 progress bar appears
- ✅ "Iteration: 0/14" shows
- ✅ Live logs start appearing
- ✅ Elapsed time counting up

#### Within 5 minutes:
- ✅ "Iteration: 1/14" updates
- ✅ "3 good / 0 buggy / 3 total nodes"
- ✅ First plot appears in Plot Gallery
- ✅ ETA shows (~25m remaining)
- ✅ Best metric displayed

#### If Error Occurs:
- ✅ Red error panel appears
- ✅ Error type and message shown
- ✅ Status changes to FAILED
- ✅ NO retry (stays failed)

## What Success Looks Like

### Run Page Should Show:

```
Run abc123...                         [RUNNING]

┌─ Error Display ───────────────────┐  (only if failed)
│ Clear error message                │
└────────────────────────────────────┘

┌─ Stage Progress ──────────────────┐
│ Stage_1: Preliminary Investigation │
│ 23% ████████░░░░░░░░░░░░░░░░      │
│ Iteration: 3/14    Elapsed: 12m    │
│ Nodes: 3 good / 1 buggy / 4 total  │
│ ETA: ~41m                           │
└────────────────────────────────────┘

┌─ Stage Timing ────────────────────┐
│ Stage_1: 12m 34s [Running]         │
│ Stage_2: --                         │
│ Stage_3: --                         │
│ Stage_4: --                         │
└────────────────────────────────────┘

┌─ Pipeline Stages ─────────────────┐
│ Stage 1: RUNNING 23%               │
│ Stage 2: PENDING                    │
│ Stage 3: PENDING                    │
│ Stage 4: PENDING                    │
└────────────────────────────────────┘

┌─ Plots ───────────────────────────┐
│ [img] [img] [img] [img]            │
│ 4 images                            │
└────────────────────────────────────┘

┌─ Live Logs ───────────────────────┐
│ [all] [info] [warn] [error]        │
│ 3:24:30 Stage_1: 3/14 good nodes   │
│ 3:24:25 Node abc123 completed      │
│ 3:24:20 Starting iteration 3       │
└────────────────────────────────────┘

┌─ Artifacts ───────────────────────┐
│ • loss_curves.png (24 KB)          │
│ • metrics.png (31 KB)               │
│ • final_paper.pdf (145 KB)          │
└────────────────────────────────────┘
```

## If Something Doesn't Work

### Debugging Steps:

1. **No status updates**
   - Check pod logs for errors
   - Verify MongoDB connection
   - Check if events collection is being populated

2. **No live progress**
   - Verify currentStage is being updated in runs collection
   - Check orchestrator logs for event processing errors
   - Ensure frontend is refetching (should see network requests every 5s)

3. **No logs appearing**
   - Check if events with type="ai.run.log" exist
   - Verify LiveLogViewer component is rendering
   - Check browser console for errors

4. **Plots not showing**
   - Verify plots are being uploaded to MinIO
   - Check artifacts collection for plot entries
   - Ensure PlotGallery component is fetching

## Rollback Plan

If deployment fails:

```bash
# On pod
cd "/workspace/AI-Scientist-v2 copy"
git checkout main
pkill -f python
python pod_worker.py
```

Then investigate issues locally before redeploying.

## Success Criteria

✅ **Run completes OR fails with clear error**  
✅ **Progress updates visible every 5-10 seconds**  
✅ **Logs stream in real-time**  
✅ **Timing shows for each stage**  
✅ **Plots visible as generated**  
✅ **Error messages clear and actionable**  
✅ **No silent failures**  
✅ **No infinite retries**  

**If all criteria met: OBSERVABILITY HEAVEN ACHIEVED** 🎉

