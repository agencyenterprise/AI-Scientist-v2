# Git Auto-Pull Feature

The pod worker includes an automatic git pull feature to keep your RunPod instances up-to-date with the latest code changes without manual intervention.

## Overview

When enabled (default), the pod worker automatically pulls the latest code from the repository at strategic times:

1. **After completing an experiment** - Before polling for the next task
2. **After completing a writeup retry** - Before polling for the next task
3. **Periodically while idle** - Every X seconds (default: 60s) when no work is queued

## Why This Matters

### Without Auto-Pull
```
1. Push code fix to GitHub
2. Pods continue running old code
3. Wait for experiments to finish
4. Manually restart each pod
5. Lose compute time during restart
```

### With Auto-Pull
```
1. Push code fix to GitHub
2. Pods automatically pull between experiments
3. New code runs on next experiment
4. Zero downtime, zero manual intervention
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GIT_AUTO_PULL_ENABLED` | `true` | Enable/disable auto-pull |
| `GIT_AUTO_PULL_INTERVAL` | `60` | Seconds between pulls when idle |
| `GIT_AUTO_PULL_BRANCH` | `feat/additions` | Branch to pull from |

### Examples

**Disable auto-pull:**
```bash
export GIT_AUTO_PULL_ENABLED=false
```

**Pull every 2 minutes when idle:**
```bash
export GIT_AUTO_PULL_INTERVAL=120
```

**Pull from main branch:**
```bash
export GIT_AUTO_PULL_BRANCH=main
```

## Behavior Details

### When Pulls Happen

#### 1. Post-Experiment Pull (Always Once)
```python
run_experiment_pipeline(run, mongo_client)
print("✅ Experiment completed!")
git_pull()  # ← Happens once here
print("🔍 Polling for next task...")
```

#### 2. Post-Writeup Pull (Always Once)
```python
perform_writeup_retry(writeup_retry, mongo_client)
print("✅ Writeup retry completed!")
git_pull()  # ← Happens once here
print("🔍 Polling for next task...")
```

#### 3. Idle Periodic Pulls (Every X Seconds)
```python
# No experiments found
if time_since_last_pull >= GIT_AUTO_PULL_INTERVAL:
    git_pull()  # ← Periodic pull during idle
    
time.sleep(10)  # Check again in 10s
```

### When Pulls DON'T Happen

- ❌ **During experiment execution** - Never interrupts running work
- ❌ **During writeup generation** - Never interrupts active tasks
- ❌ **If disabled** - Respects the `GIT_AUTO_PULL_ENABLED` setting

### Pull Process

Each git pull operation:

1. **Fetches** latest changes from `origin/{branch}`
2. **Checks** if there are new commits to pull
3. **Skips** if already up-to-date (silent)
4. **Pulls** if commits are available
5. **Reports** number of commits pulled
6. **Warns** if `pod_worker.py` itself was updated

Example output:
```
📥 Pulling latest changes from git (feat/additions)... ✓ Pulled 3 new commit(s)
⚠️  pod_worker.py was updated - please restart this worker to use new version
   (Worker will continue with current version for now)
```

## Safety Features

### 1. Non-Disruptive
Pulls only happen between experiments, ensuring:
- No interruption of running experiments
- No corruption of experiment state
- No race conditions with file writes

### 2. Graceful Failure
If a pull fails:
- Error is logged with details
- Worker continues with current code
- Next scheduled pull will retry

### 3. Self-Update Detection
If `pod_worker.py` is updated:
- Worker prints a warning
- Suggests manual restart
- Continues running current version (no automatic restart)

### 4. Timeout Protection
All git operations have timeouts:
- Fetch: 30 seconds
- Pull: 30 seconds
- Status checks: 10 seconds

### 5. Idempotent
- Safe to pull multiple times
- "Already up-to-date" is handled gracefully
- No duplicate pulls if nothing changed

## Example Log Output

### Startup
```
============================================================
🤖 AI Scientist Pod Worker
============================================================
Pod ID: abc123xyz
Control Plane: https://ai-scientist-v2-production.up.railway.app
Git Auto-Pull: Enabled (every 60s when idle)
Git Branch: feat/additions
============================================================

✓ Connected to MongoDB

🔍 Polling for experiments and writeup retries...
```

### During Idle Polling
```
⏱️  No experiments or retries available, waiting 10s...
⏱️  No experiments or retries available, waiting 10s...
⏱️  No experiments or retries available, waiting 10s...
⏱️  No experiments or retries available, waiting 10s...
⏱️  No experiments or retries available, waiting 10s...
⏱️  No experiments or retries available, waiting 10s...
📥 Pulling latest changes from git (feat/additions)... ✓ Already up to date
⏱️  No experiments or retries available, waiting 10s...
```

### After Experiment Completes
```
✅ Experiment completed!
🔄 Checking for code updates...
📥 Pulling latest changes from git (feat/additions)... ✓ Pulled 2 new commit(s)

🔍 Polling for next task...
```

### When pod_worker.py Changes
```
✅ Experiment completed!
🔄 Checking for code updates...
📥 Pulling latest changes from git (feat/additions)... ✓ Pulled 1 new commit(s)
⚠️  pod_worker.py was updated - please restart this worker to use new version
   (Worker will continue with current version for now)

🔍 Polling for next task...
```

## Integration with Setup Scripts

The `setup_and_run.sh` and `init_runpod.sh` scripts automatically:

1. Set up SSH authentication for git
2. Clone the repository
3. Configure the git remote
4. Start the worker with auto-pull enabled

No additional configuration needed!

## Troubleshooting

### Pull Fails with "Not a git repository"
**Cause:** Worker not running from repository root

**Solution:** Ensure worker is started from `/workspace/AI-Scientist-v2`

### Pull Fails with "Permission denied"
**Cause:** SSH key not configured or expired

**Solution:** 
1. Verify `GIT_SSH_KEY_AI_SCIENTIST_V2_B64` is set
2. Test SSH: `ssh -T git@github.com-AI-Scientist-v2`
3. Re-run `setup_and_run.sh`

### Pull Fails with "Your local changes would be overwritten"
**Cause:** Local modifications in the repository

**Solution:**
```bash
cd /workspace/AI-Scientist-v2
git stash
git pull origin feat/additions
```

### Warning Shows but Worker Still Running Old Code
**Cause:** `pod_worker.py` was updated but worker is already loaded in memory

**Solution:** Restart the worker:
```bash
# Press Ctrl+C to stop
# Then restart:
python pod_worker.py
```

### Pulls Too Frequent/Infrequent
**Cause:** Default 60s interval not optimal for your use case

**Solution:** Adjust the interval:
```bash
# Faster (every 30s)
export GIT_AUTO_PULL_INTERVAL=30

# Slower (every 5 minutes)
export GIT_AUTO_PULL_INTERVAL=300
```

## Best Practices

### For Development
- Keep auto-pull enabled
- Use a reasonable interval (30-120s)
- Monitor logs for pull notifications
- Restart workers after critical `pod_worker.py` changes

### For Production
- Keep auto-pull enabled
- Use longer intervals (120-300s) to reduce log noise
- Set up alerts for pull failures
- Have a process to restart all workers after major updates

### For Testing
- Consider disabling auto-pull (`GIT_AUTO_PULL_ENABLED=false`)
- Manually control when to pull updates
- Easier to reproduce issues with known code versions

## Performance Impact

- **Minimal overhead** - Only checks for updates, doesn't pull if up-to-date
- **No experiment impact** - Pulls happen between experiments only
- **Network efficient** - Uses git fetch + pull (not full clone)
- **Fast operations** - Typical pull takes < 1 second when up-to-date

## Technical Details

### Implementation

The git pull logic is implemented in `pod_worker.py`:

```python
def git_pull():
    """Pull latest changes from git repository."""
    # 1. Fetch latest changes
    git fetch origin {branch}
    
    # 2. Check if behind
    commits_behind = git rev-list --count HEAD..origin/{branch}
    
    # 3. Pull if needed
    if commits_behind > 0:
        git pull origin {branch}
        
    # 4. Check if pod_worker.py changed
    if "pod_worker.py" in changed_files:
        warn_user_to_restart()
```

### Git Commands Used

```bash
git fetch origin feat/additions
git rev-list --count HEAD..origin/feat/additions
git pull origin feat/additions
git diff --name-only HEAD~N HEAD
```

All commands run with:
- `cwd=repo_dir` - Correct working directory
- `timeout=30` - Prevents hanging
- `capture_output=True` - Logs are captured

## Related Documentation

- [RUNPOD_QUICK_START.md](./RUNPOD_QUICK_START.md) - Full RunPod setup guide
- [POD_WORKER_GUIDE.md](./POD_WORKER_GUIDE.md) - Pod worker architecture
- [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md) - Deployment steps

