# Complete Observability System - Deployment Guide

## What This System Provides

### Real-Time Monitoring
- ✅ **Live Progress**: Updates every 5 seconds with current iteration/max
- ✅ **Stage Timing**: Elapsed time + ETA for each stage
- ✅ **Node Tracking**: Good nodes vs buggy nodes with counts
- ✅ **Best Metrics**: Current best performance metrics displayed live
- ✅ **Log Streaming**: Live logs with filtering (info/warn/error)
- ✅ **Plot Gallery**: Plots uploaded and displayed as they're generated
- ✅ **Error Display**: Clear error messages when failures occur

### No More Silent Failures
- ❌ **Auto-retry DISABLED**: Experiments stop on first error
- ✅ **Error surfaced**: Type, message, and timestamp shown in UI
- ✅ **Human intervention**: Must fix issue before retrying

### Clean Architecture
- ✅ **Single folder per run**: Retries reuse existing directory
- ✅ **Auto-cleanup**: Archives to MinIO and cleans local on completion
- ✅ **Event-driven**: All updates flow through CloudEvents spec

## Files Changed

### Backend (Pod Worker)
1. `pod_worker.py` - Core worker with event emission, .env loading, error handling
2. `monitor_experiment.py` - File watcher for live updates (backup system)
3. `ai_scientist/treesearch/perform_experiments_bfts_with_agentmanager.py` - Event callbacks
4. `idea_processor.py` - Database name fix (ai-scientist)
5. `init_runpod.sh` - Auto-loads env vars to bashrc
6. `start_worker.sh` - Helper script

### Frontend (Orchestrator)
1. `orchestrator/apps/web/lib/schemas/run.ts` - Enhanced schema
2. `orchestrator/apps/web/lib/schemas/cloudevents.ts` - Updated event schemas
3. `orchestrator/apps/web/lib/services/events.service.ts` - Populates all fields
4. `orchestrator/apps/web/lib/services/ideation.service.ts` - Auto-generate ideaJson
5. `orchestrator/apps/web/app/api/hypotheses/route.ts` - Calls ideation service
6. `orchestrator/apps/web/app/api/runs/[id]/events/route.ts` - Event query API
7. `orchestrator/apps/web/components/RunDetailClient.tsx` - Main UI updates
8. `orchestrator/apps/web/components/ErrorDisplay.tsx` - NEW
9. `orchestrator/apps/web/components/StageProgressPanel.tsx` - NEW
10. `orchestrator/apps/web/components/StageTimingView.tsx` - NEW
11. `orchestrator/apps/web/components/LiveLogViewer.tsx` - NEW
12. `orchestrator/apps/web/components/PlotGallery.tsx` - NEW
13. `orchestrator/apps/web/package.json` - Added openai dependency

### Testing
1. `tests/integration/test_full_pipeline.py` - Integration tests

## Deployment Steps

### 1. Deploy Frontend (Railway/Vercel)

```bash
cd orchestrator/apps/web
pnpm install  # Install openai package
pnpm build
# Deploy to Railway (auto-deploys on push)
```

### 2. Deploy to Pod (RunPod)

```bash
# SSH into your pod
# Then:

cd "/workspace/AI-Scientist-v2 copy"

# Pull latest code
git pull origin feat/additions

# Verify .env exists with API keys
cat .env

# If .env is missing, create it:
cat > .env << 'EOF'
OPENAI_API_KEY=your_key_here
MONGODB_URL=your_mongodb_url_here
CONTROL_PLANE_URL=https://ai-scientist-v2-production.up.railway.app
EOF

# Kill any running workers
pkill -f pod_worker.py
pkill -f monitor_experiment.py

# Start worker with new code
python pod_worker.py
```

### 3. Test the System

```bash
# Run integration tests locally
cd /path/to/AI-Scientist-v2
source .venv/bin/activate
pytest tests/integration/test_full_pipeline.py -v
```

### 4. Create Test Hypothesis

1. Go to frontend: Hypotheses tab
2. Create a simple hypothesis:
   - Title: "Test Observability"
   - Idea: "Test the observability system with a minimal experiment"
3. Watch the run page - you should see:
   - Status changes: QUEUED → SCHEDULED → RUNNING
   - Live progress panel with iteration count
   - Stage timing with elapsed time + ETA
   - Live logs streaming
   - Plots appearing as generated
   - Error display if anything fails

## What You'll See

### When Running:
```
┌─ Stage Progress Panel ─────────────────────────┐
│ Stage_1: Preliminary Investigation        23%  │
│ ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░      │
│                                                 │
│ Iteration: 3/14              Elapsed: 12m 34s  │
│ Nodes: 3 good / 8 buggy / 11 total  ETA: ~41m  │
│                                                 │
│ Best Metric: validation_loss=0.0184            │
└─────────────────────────────────────────────────┘
```

### When Failed:
```
┌─ Error Display ────────────────────────────────┐
│ ❌ Experiment Failed                            │
│                                                 │
│ AuthenticationError                             │
│ Incorrect API key provided: sk-proj-...         │
│                                                 │
│ Failed at 10/23/2025, 3:24:42 PM               │
│                                                 │
│ [View Full Traceback] [Retry Run]              │
└─────────────────────────────────────────────────┘
```

## Troubleshooting

### No Events Appearing
1. Check pod logs: `tail -f /workspace/AI-Scientist-v2\ copy/pod_worker.py`
2. Verify events in DB: Check MongoDB `ai-scientist` database, `events` collection
3. Check orchestrator logs for event processing errors

### API Key Errors
1. Verify .env file exists on pod
2. Check OPENAI_API_KEY is set: `echo $OPENAI_API_KEY`
3. Worker now loads .env at start of each experiment

### Monitor Not Working
1. Kill old monitors: `pkill -f monitor_experiment.py`
2. Restart: `python /workspace/monitor_experiment.py <run_id>`
3. Check logs: `tail -f monitor.log`

## Key Improvements Made

1. **Database**: Use `ai-scientist` (with dash) consistently
2. **Retry Logic**: DISABLED - fails fast, shows error
3. **Folder Management**: Reuses directory on retry
4. **Event Emission**: Every iteration, with full context
5. **Frontend**: Rich components showing all data
6. **Error Handling**: Clear error messages, no silent failures
7. **Timing**: Track elapsed + ETA for all stages
8. **Cleanup**: Archives to MinIO and removes local files

## Next Steps

After deployment, you should see:
- Real-time progress updates
- Clear error messages
- No wasted compute on infinite retries
- Full visibility into experiment state

If anything fails, you'll know **immediately** and **exactly why**.

