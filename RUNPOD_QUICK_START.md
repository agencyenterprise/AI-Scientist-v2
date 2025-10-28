# RunPod Quick Start Guide

## 🚀 One-Command Setup

This guide shows you how to get AI Scientist v2 running on a fresh RunPod instance with a single command.

## Prerequisites

You must have the following environment variable set in your RunPod template or pod:

- `GIT_SSH_KEY_AI_SCIENTIST_V2_B64` - Base64-encoded SSH deploy key for the repository

## Setup Instructions

### One-Command Setup (Recommended)

Run this single command in your RunPod terminal:

```bash
curl -fsSL https://gist.githubusercontent.com/flaviokicis/f4248809521b2443b534ca077e042e08/raw/setup_and_run.sh | bash
```

That's it! ✨

The script will automatically:
- Install git and SSH client
- Set up SSH authentication using your deploy key
- Clone the repository
- Install all dependencies (Anaconda, PyTorch, LaTeX, etc.)
- Start the pod worker

---

### Alternative: Download and Run

If you prefer to review the script first:

```bash
# Download the script
curl -fsSL https://gist.githubusercontent.com/flaviokicis/f4248809521b2443b534ca077e042e08/raw/setup_and_run.sh > setup_and_run.sh

# Review it (optional)
cat setup_and_run.sh

# Make executable and run
chmod +x setup_and_run.sh
./setup_and_run.sh
```

**Gist URL:** https://gist.github.com/flaviokicis/f4248809521b2443b534ca077e042e08

## What the Script Does

The `setup_and_run.sh` script automatically:

1. ✅ Installs git and SSH client (if needed)
2. ✅ Configures SSH authentication using your deploy key
3. ✅ Tests SSH connection to GitHub
4. ✅ Clones the repository (or updates if already exists)
5. ✅ Checks out the `feat/additions` branch
6. ✅ Runs `init_runpod.sh` which:
   - Installs Anaconda
   - Creates conda environment
   - Installs all Python dependencies
   - Installs PyTorch with CUDA support
   - Installs LaTeX and system packages
   - Configures environment persistence
7. ✅ Starts the pod worker automatically

## After Setup

Once the script completes:

- The pod worker will be running and polling for experiments
- All environment variables are persisted in `~/.bashrc`
- The conda environment auto-activates in new shells
- You can stop the worker with `Ctrl+C`
- **Git auto-pull is enabled** - the pod stays updated automatically

## Git Auto-Pull Feature

The pod worker automatically pulls the latest code to ensure it's always up-to-date:

### When Git Pull Happens

1. **After each experiment completes** - Pulls once before polling for the next task
2. **After each writeup retry completes** - Ensures latest code for next task
3. **Every 60 seconds while idle** - Keeps checking for updates when no work is available

### How It Works

```
Experiment Running → [No pulls during execution]
   ↓
Experiment Completes
   ↓
Git Pull (once) ← Ensures latest code before next task
   ↓
Polling for next experiment
   ↓
If idle for 60s → Git Pull ← Periodic check
   ↓
Still idle for 60s → Git Pull ← Periodic check
   ↓
New experiment found → Start running (no pulls)
```

### Benefits

- ✅ Pods always run the latest bug fixes
- ✅ No need to manually restart pods after code changes
- ✅ Zero downtime - pulls happen between experiments
- ✅ Smart detection - warns if `pod_worker.py` itself is updated

### Configuration

Control the behavior with environment variables:

```bash
# Disable auto-pull completely
GIT_AUTO_PULL_ENABLED=false

# Pull every 2 minutes when idle (default: 60s)
GIT_AUTO_PULL_INTERVAL=120

# Pull from a different branch (default: feat/additions)
GIT_AUTO_PULL_BRANCH=main
```

### Important Notes

- Pulls only happen **between** experiments, never during execution
- If `pod_worker.py` is updated, you'll see a warning to manually restart
- Git pull failures are logged but don't stop the worker
- The worker continues with its current version if pulls fail

## Restarting the Worker

If you need to restart the worker later:

```bash
cd /workspace/AI-Scientist-v2
python pod_worker.py
```

No need to rerun the setup script or activate conda - it's all automatic!

## Pulling Latest Changes

To update to the latest code:

```bash
cd /workspace/AI-Scientist-v2
git pull origin feat/additions
```

## Troubleshooting

### SSH Authentication Failed

If SSH authentication fails, verify your environment variable:

```bash
echo "${GIT_SSH_KEY_AI_SCIENTIST_V2_B64:0:50}..."
```

You should see base64-encoded text. If empty, the variable isn't set.

### Repository Clone Failed

Check that the SSH host alias is correct:

```bash
ssh -T git@github.com-AI-Scientist-v2
```

Expected output: `Hi agencyenterprise! You've successfully authenticated...`

### init_runpod.sh Not Found

The script expects the repository at `/workspace/AI-Scientist-v2`. If you see this error, check:

```bash
ls -la /workspace/AI-Scientist-v2
```

## Repository Location

- **Default path**: `/workspace/AI-Scientist-v2`
- **Branch**: `feat/additions`
- **SSH alias**: `git@github.com-AI-Scientist-v2:agencyenterprise/AI-Scientist-v2.git`

## Environment Variables Required

These should be set in your RunPod template:

### Required Variables
- `GIT_SSH_KEY_AI_SCIENTIST_V2_B64` - SSH deploy key (base64)
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key  
- `MONGODB_URL` - MongoDB connection string
- `MONGODB_DB_NAME` - MongoDB database name
- `S3_ENDPOINT_URL` - S3 endpoint URL
- `S3_ACCESS_KEY_ID` - S3 access key
- `S3_SECRET_ACCESS_KEY` - S3 secret key
- `S3_BUCKET_NAME` - S3 bucket name

### Optional Variables (Git Auto-Pull)
- `GIT_AUTO_PULL_ENABLED` - Enable automatic git pulls (default: `true`)
- `GIT_AUTO_PULL_INTERVAL` - Seconds between pulls when idle (default: `60`)
- `GIT_AUTO_PULL_BRANCH` - Branch to pull from (default: `feat/additions`)

## Notes

- The setup script is idempotent - safe to run multiple times
- If the repo already exists, it will pull latest changes instead of cloning
- All logs are visible during setup for debugging
- The pod worker starts automatically at the end

