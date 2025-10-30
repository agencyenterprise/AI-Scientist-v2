# Pod Worker Guide

This guide explains how to set up and run the AI Scientist pod worker on RunPod (or any GPU machine).

## Architecture Overview

The system uses a **pull-based architecture** where pods autonomously fetch work from MongoDB:

```
┌─────────────────┐         ┌──────────────────┐         ┌──────────────┐
│  Frontend UI    │────────▶│  Next.js Backend │────────▶│   MongoDB    │
│  (Web Browser)  │         │  (Railway)       │         │              │
└─────────────────┘         └──────────────────┘         └──────────────┘
                                     ▲                            ▲
                                     │                            │
                                     │ CloudEvents                │ Atomic Fetch
                                     │ (NDJSON)                   │ (findOneAndUpdate)
                                     │                            │
                            ┌────────┴────────┐          ┌────────┴────────┐
                            │  Pod Worker 1   │          │  Pod Worker N   │
                            │   (RunPod)      │   ...    │   (RunPod)      │
                            └─────────────────┘          └─────────────────┘
```

### Key Features

- **No race conditions**: MongoDB's `findOneAndUpdate` is atomic
- **No Redis needed**: MongoDB IS the queue
- **Idempotent events**: Duplicate events are safely ignored via event ID + seq tracking
- **Universal error handling**: All exceptions automatically reported to frontend
- **Real-time updates**: Frontend sees everything via MongoDB polling
- **Auto-recovery**: Workers can crash/restart safely; runs are tracked by `claimedBy`

## Setup on RunPod

### 1. Initial Setup (First Time Only)

```bash
# Clone the repo (if not already done)
git clone https://github.com/your-org/AI-Scientist-v2.git
cd AI-Scientist-v2

# Create .env file with your credentials
cat > .env << EOF
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/ai_scientist
CONTROL_PLANE_URL=https://ai-scientist-v2-production.up.railway.app
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
EOF

# Run initialization (installs conda, packages, etc.)
bash init_runpod.sh
```

**Note**: `init_runpod.sh` will now automatically start the pod worker at the end. If you want to stop it, press `Ctrl+C`.

### 2. Starting the Worker Manually

If you stopped the worker or opened a new terminal:

```bash
# Option 1: Use the helper script (recommended)
./start_worker.sh

# Option 2: Manual activation
source ~/.bashrc
conda activate ai_scientist
python pod_worker.py
```

### 2a. Dedicated Ideation Workers

Ideation now runs on its own queue so experimentation pods stay focused. To launch a worker that only processes ideation requests, pass the new mode flag:

```bash
# Run the worker in ideation-only mode
./start_worker.sh --mode ideation

# Equivalent manual invocation
python pod_worker.py --mode ideation
```

You can also set `WORKER_MODE=ideation` in the environment before starting the worker. The default remains `experiment`, and `hybrid` will service both queues (ideation tasks are claimed first).

### 3. Environment Variables

Required:
- `MONGODB_URL`: MongoDB connection string (must have read/write access to `runs`, `hypotheses`, `events`, etc.)
- `OPENAI_API_KEY`: OpenAI API key for LLM calls

Optional:
- `CONTROL_PLANE_URL`: Backend URL (defaults to production Railway URL)
- `ANTHROPIC_API_KEY`: Anthropic API key (if using Claude models)
- `RUNPOD_POD_ID`: Pod identifier (auto-detected if not set)

## How It Works

### Experiment Flow

1. **User creates hypothesis** via frontend.
   - If *Enable ideation* is checked, the frontend creates an entry in `ideation_requests` and marks the hypothesis with `ideation.status = "QUEUED"`.
   - Otherwise, the frontend immediately creates a run in MongoDB with `status: "QUEUED"` (legacy behaviour).
2. **Ideation workers poll** `ideation_requests` (when running in `--mode ideation` or `--mode hybrid`). They call `perform_ideation_temp_free.py` (model `gpt-5-mini`) and push ideas back onto the hypothesis, selecting the first idea as `ideaJson`.
3. **Experiment pods poll** the `runs` collection every ~10 seconds.
4. **Experiment worker atomically claims a run** via `findOneAndUpdate`:
   ```python
   runs.find_one_and_update(
       {"status": "QUEUED", "claimedBy": None},
       {"$set": {"status": "SCHEDULED", "claimedBy": pod_id, ...}}
   )
   ```
5. **Worker runs experimentation pipeline**:
   - Run 4 stages (Stage_1 through Stage_4)
   - Generate plots
   - Generate paper (LaTeX → PDF)
   - Run auto-validation (LLM review)
   - Upload artifacts to MinIO
6. **Worker emits events** throughout (batch NDJSON to `/api/ingest/events`)
7. **Backend updates MongoDB** based on events
8. **Frontend shows live updates** via MongoDB queries

### Event Types

The worker emits CloudEvents in these categories:

**Lifecycle:**
- `ai.run.started` - Run begins
- `ai.run.heartbeat` - Liveness ping
- `ai.run.failed` - Terminal failure
- `ai.run.canceled` - User canceled

**Stages:**
- `ai.run.stage_started` - Stage begins
- `ai.run.stage_progress` - Progress update (0.0 to 1.0)
- `ai.run.stage_metric` - Metric value (e.g., loss, accuracy)
- `ai.run.stage_completed` - Stage finished

**Ideation & Paper:**
- `ai.ideation.generated` - Ideas generated
- `ai.paper.generated` - Paper PDF created

**Validation:**
- `ai.validation.auto_started` - Auto-validation begins
- `ai.validation.auto_completed` - Auto-validation finishes (verdict: pass/fail)

**Artifacts:**
- `ai.artifact.registered` - File uploaded to MinIO
- `ai.artifact.failed` - Upload failed

**Logs:**
- `ai.run.log` - Structured log line

### Error Handling

The worker has **universal error handling** that catches ALL exceptions:

```python
# Global exception handler (sys.excepthook)
# + StageContext __exit__ handler
# + try/except in main loop

# Any exception automatically emits:
{
  "type": "ai.run.failed",
  "data": {
    "run_id": "...",
    "stage": "Stage_2",
    "code": "OOMError",
    "message": "CUDA out of memory",
    "traceback": "...",
    "retryable": false
  }
}
```

**No need to add try/catch everywhere!** Just run your code and any error will be reported to the frontend.

### Special Error Cases

The worker handles BFTS-specific errors:

- **All nodes buggy**: Emits `ai.run.failed` with `code: "ALL_NODES_BUGGY"`
- **Max iterations hit**: Emits `ai.run.failed` with `code: "MAX_ITERATIONS"`
- **OOM**: Automatically detected and reported
- **Timeout**: Reported with `retryable: true`

## Monitoring

### Check Worker Status

```bash
# View worker logs
tail -f worker.log  # If you redirect output

# Check MongoDB for claimed runs
mongo $MONGODB_URL --eval 'db.runs.find({claimedBy: "pod_abc123"})'

# Check if worker is running
ps aux | grep pod_worker
```

### Frontend Views

- **Runs page** (`/runs`): See all runs and their statuses
- **Run detail** (`/runs/[id]`): See stages, artifacts, events, validations
- **Queue status** (`/` homepage): See QUEUED, RUNNING, AWAITING_HUMAN counts

### Debugging

If a run gets stuck:

1. Check worker logs for exceptions
2. Check `/runs/[id]` page for last event
3. Check `events` collection in MongoDB
4. Look at `lastEventSeq` on the run document

If worker crashes:

1. Restart with `./start_worker.sh`
2. Worker will pick up any `QUEUED` runs
3. Partially completed runs will stay `RUNNING` (safe; you can manually reset to `QUEUED` if needed)

## Testing

### Test Event Ingestion

```bash
# Send a test event
curl -X POST https://ai-scientist-v2-production.up.railway.app/api/ingest/event \
  -H "Content-Type: application/cloudevents+json" \
  -d '{
    "specversion": "1.0",
    "id": "test-123",
    "source": "test://local",
    "type": "ai.run.heartbeat",
    "subject": "run/test-run-id",
    "time": "2025-10-22T19:00:00Z",
    "datacontenttype": "application/json",
    "data": {"run_id": "test-run-id", "gpu_util": 0.75}
  }'
```

### Test Batch Ingestion

```bash
# Send NDJSON batch
curl -X POST https://ai-scientist-v2-production.up.railway.app/api/ingest/events \
  -H "Content-Type: application/x-ndjson" \
  -d $'{"specversion":"1.0","id":"test-1","source":"test://local","type":"ai.run.heartbeat","subject":"run/test-run-id","time":"2025-10-22T19:00:00Z","datacontenttype":"application/json","data":{"run_id":"test-run-id"}}\n{"specversion":"1.0","id":"test-2","source":"test://local","type":"ai.run.heartbeat","subject":"run/test-run-id","time":"2025-10-22T19:00:01Z","datacontenttype":"application/json","data":{"run_id":"test-run-id"}}'
```

## Scaling

To run multiple pods:

1. Start `init_runpod.sh` on each pod (with same `MONGODB_URL`)
2. Each pod gets a unique `RUNPOD_POD_ID` (auto-detected)
3. MongoDB ensures only ONE pod claims each run (atomic operation)
4. All pods emit events to the same control plane

**No configuration needed!** Just start more workers.

## Troubleshooting

### Worker won't start

- Check `MONGODB_URL` is set and valid
- Check MongoDB connectivity: `mongo $MONGODB_URL --eval 'db.stats()'`
- Check Python packages installed: `pip list | grep ulid`

### Events not showing in frontend

- Check network connectivity to control plane
- Check `/api/ingest/events` endpoint returns 202
- Check MongoDB `events` collection has new docs
- Check browser console for errors

### Runs stuck in QUEUED

- Check worker is running: `ps aux | grep pod_worker`
- Check MongoDB query: `db.runs.find({status: "QUEUED"})`
- Check worker logs for errors

### GPU not detected

- Check CUDA: `nvidia-smi`
- Check PyTorch: `python -c "import torch; print(torch.cuda.is_available())"`
- Re-run Step 11 in `init_runpod.sh` (PyTorch installation)

## Architecture Decisions

### Why MongoDB as Queue?

- **Already have it**: No new infrastructure
- **Atomic operations**: `findOneAndUpdate` prevents race conditions
- **Rich queries**: Can filter by priority, hypothesis, etc.
- **Single source of truth**: Frontend reads same DB

### Why CloudEvents?

- **Standard**: Vendor-neutral, well-documented
- **Extensible**: Easy to add new event types
- **Tooling**: Can use off-the-shelf validators/routers later

### Why NDJSON Batching?

- **Efficient**: Send 50 events in one request
- **Streaming**: Can parse line-by-line
- **Simple**: No complex protocol, just newline-delimited JSON

### Why No Authentication (Yet)?

- **Simplicity**: Get it working first
- **Private network**: Railway ↔ RunPod is trusted
- **Future-proof**: Can add auth headers later without changing event shapes

## Next Steps

### Immediate (MVP)

- [x] Backend ingest endpoints
- [x] Event processor with MongoDB mappers
- [x] Pod worker with atomic fetch
- [x] Global error handling
- [ ] Test with real RunPod instance

### Soon

- [ ] Add `priority` field to runs (high priority runs first)
- [ ] Add heartbeat monitoring (auto-fail stale runs)
- [ ] Add retry logic (auto-requeue failed runs if `retryable: true`)
- [ ] Add `/hypotheses/[id]` page (show ideation results)
- [ ] Add real-time event log viewer (`/runs/[id]/events`)

### Later

- [ ] Add authentication (API keys or signatures)
- [ ] Add distributed tracing (W3C Trace Context)
- [ ] Add metrics dashboard (events/sec, error rates)
- [ ] Add multi-region support (region-specific queues)
- [ ] Add cost tracking (track tokens, GPU hours)

## Support

Questions? Issues?

- Check logs first
- Check MongoDB state
- Check this guide's Troubleshooting section
- Ask in #ai-scientist Slack channel
