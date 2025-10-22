# Quick Start Guide

## 🚀 Get Everything Running in 5 Minutes

### Step 1: Deploy Backend (Railway)

```bash
cd orchestrator/apps/web

# The new endpoints are already implemented:
# - POST /api/ingest/events (NDJSON batch)
# - POST /api/ingest/event (single CloudEvents)

# Just deploy normally - no new env vars needed
git add .
git commit -m "Add CloudEvents ingestion endpoints"
git push origin feat/additions
```

Railway will auto-deploy. The endpoints will be live at:
- `https://ai-scientist-v2-production.up.railway.app/api/ingest/events`
- `https://ai-scientist-v2-production.up.railway.app/api/ingest/event`

### Step 2: Test Endpoints (Optional but Recommended)

```bash
# From your local machine
cd /Users/jessica/AEStudio/agi/AI-Scientist-v2

# Activate your venv
source .venv/bin/activate

# Install test dependencies
pip install requests python-ulid

# Run tests
python test_event_ingestion.py
```

Expected output:
```
✅ Single event test PASSED
✅ Batch event test PASSED
✅ Duplicate detection test PASSED
✅ Invalid event rejection test PASSED
🎉 ALL TESTS PASSED
```

### Step 3: Set Up RunPod

#### A. Create .env File

On your RunPod instance:

```bash
cd AI-Scientist-v2

cat > .env << 'EOF'
MONGODB_URL=mongodb+srv://user:password@cluster.mongodb.net/ai_scientist
CONTROL_PLANE_URL=https://ai-scientist-v2-production.up.railway.app
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
EOF
```

#### B. Run Initialization

```bash
bash init_runpod.sh
```

This will:
1. Install Anaconda
2. Create `ai_scientist` conda environment
3. Install all Python dependencies (including `python-ulid`)
4. Install PyTorch with CUDA
5. **Start the pod worker automatically**

The worker will start polling for experiments immediately!

### Step 4: Create Your First Experiment

#### Via Frontend:

1. Go to `https://ai-scientist-v2-production.up.railway.app/hypotheses`
2. Create a new hypothesis:
   - **Title:** "Test Compositional Regularization"
   - **Idea:** "Investigate how compositional regularization affects neural network generalization..."
3. Click "Create Hypothesis"
4. Frontend auto-creates a run with `status: QUEUED`
5. Within 10 seconds, pod worker picks it up!

#### Via MongoDB (Advanced):

```bash
# Using manage_runs.py
python manage_runs.py list
python manage_runs.py show <run_id>
```

### Step 5: Monitor Progress

**Watch Worker Logs:**
```bash
# On RunPod
tail -f /workspace/AI-Scientist-v2/worker.log  # if you redirected output
# OR just watch terminal output
```

**Check Frontend:**
- Homepage: Queue status
- `/runs`: All runs
- `/runs/[id]`: Detailed run view with stages, events, artifacts

**Check MongoDB:**
```bash
python manage_runs.py stats
```

Expected output:
```
Queue Statistics
====================================
QUEUED                     0
RUNNING                    1
AUTO_VALIDATING            0
AWAITING_HUMAN             2
...
```

## 🎯 What to Expect

### Timeline (Per Experiment)

| Stage | Duration | What Happens |
|-------|----------|--------------|
| **Ideation** | 2-5 min | Generate ideas from hypothesis text (only if needed) |
| **Stage 1** | 10-20 min | Preliminary investigation |
| **Stage 2** | 15-30 min | Baseline tuning |
| **Stage 3** | 20-40 min | Research agenda execution |
| **Stage 4** | 15-30 min | Ablation studies |
| **Plotting** | 1-2 min | Aggregate experiment plots |
| **Paper** | 5-10 min | Generate LaTeX, compile PDF |
| **Validation** | 2-3 min | LLM review |
| **Total** | 70-140 min | ~1-2 hours per experiment |

### Events You'll See

```
ai.run.started              → Frontend: Status = RUNNING
ai.run.stage_started        → Frontend: Shows stage name
ai.run.stage_progress       → Frontend: Progress bar updates
ai.run.stage_completed      → Frontend: Stage marked complete
ai.paper.generated          → Frontend: Paper available for download
ai.validation.auto_completed → Frontend: Status = AWAITING_HUMAN
```

### Artifacts Generated

- `paper.pdf` - Main paper (4 pages, ICBINB format)
- `*.png` - Figures (loss curves, etc.)
- `idea.json` - Structured idea
- `idea.md` - Markdown idea

All uploaded to MinIO, accessible via frontend.

## 🐛 Troubleshooting

### Worker won't start

**Check environment variables:**
```bash
echo $MONGODB_URL
echo $CONTROL_PLANE_URL
echo $OPENAI_API_KEY
```

If missing, load `.env`:
```bash
source .env  # For bash
# OR
export $(cat .env | xargs)
```

### No runs being picked up

**Check worker is running:**
```bash
ps aux | grep pod_worker
```

**Check MongoDB connection:**
```bash
python -c "from pymongo import MongoClient; print(MongoClient('$MONGODB_URL').admin.command('ping'))"
```

**Check runs exist:**
```bash
python manage_runs.py list --status QUEUED
```

### Run stuck in RUNNING

**Check worker logs for errors**

**Reset run to retry:**
```bash
python manage_runs.py reset <run_id>
```

**Cancel run:**
```bash
python manage_runs.py cancel <run_id>
```

### Events not showing in frontend

**Check endpoint is reachable:**
```bash
curl https://ai-scientist-v2-production.up.railway.app/api/health
```

**Check MongoDB for events:**
```bash
python manage_runs.py show <run_id>
# Shows event count at bottom
```

**Test event ingestion:**
```bash
python test_event_ingestion.py
```

## 🔄 Restart Worker

If worker crashes or you want to restart:

```bash
# Stop worker (Ctrl+C if running in foreground)

# Restart
./start_worker.sh
```

Worker will resume polling immediately. Any `QUEUED` runs will be picked up.

## 📊 Multiple Pods

To scale horizontally:

1. Spin up multiple RunPod instances
2. Run `init_runpod.sh` on each (with same `.env`)
3. Each pod gets unique `RUNPOD_POD_ID` (auto-detected)
4. MongoDB ensures ONE pod per run (atomic!)

**No coordination needed!** Just start more workers.

## ✅ Success Checklist

- [ ] Backend deployed to Railway
- [ ] Endpoints tested (`test_event_ingestion.py` passes)
- [ ] RunPod initialized (`init_runpod.sh` complete)
- [ ] Worker running (`ps aux | grep pod_worker`)
- [ ] Created test hypothesis via frontend
- [ ] Run picked up by worker (status = RUNNING)
- [ ] Saw events in frontend (stages updating)
- [ ] Paper generated and downloadable
- [ ] Auto-validation completed (status = AWAITING_HUMAN)

## 🎉 You're Done!

The system is now fully operational. Just create hypotheses via the frontend and watch the magic happen.

**Pro tips:**
- Use `manage_runs.py` to inspect runs from CLI
- Check worker logs if something seems stuck
- Reset runs to `QUEUED` if they fail and you want to retry
- Scale horizontally by adding more pods (they'll share the queue)

## 📚 More Info

- `POD_WORKER_GUIDE.md` - Detailed architecture and troubleshooting
- `IMPLEMENTATION_SUMMARY.md` - Technical details and file changes
- `test_event_ingestion.py` - Test examples
- `manage_runs.py --help` - CLI usage

---

**Questions? Issues?**  
Check `POD_WORKER_GUIDE.md` first, then ask in #ai-scientist Slack!

