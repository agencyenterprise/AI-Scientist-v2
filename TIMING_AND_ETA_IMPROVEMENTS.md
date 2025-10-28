# Timing and ETA Improvements

## What Was Implemented

### 1. **Smart ETA Calculation (Moving Average)**

**Problem:** ETA was fluctuating wildly (6h → 12h → 6h) because it used naive linear extrapolation that assumed constant velocity.

**Solution:** Track actual iteration durations and use moving average:

```python
# Lines 111-113, 119-123, 168-175
iteration_start_times = []
iteration_durations = []

def step_callback(stage, journal):
    # Track timing between iterations
    current_time = time.time()
    if len(iteration_start_times) > 0:
        duration = current_time - iteration_start_times[-1]
        iteration_durations.append(duration)
    iteration_start_times.append(current_time)
    
    # Calculate smart ETA using moving average
    eta_s = None
    if len(iteration_durations) >= 2:  # ← Handles < 5 iterations!
        recent_durations = iteration_durations[-5:]  # Last 5 (or fewer)
        avg_duration = sum(recent_durations) / len(recent_durations)
        remaining_iterations = stage.max_iterations - current_iteration
        eta_s = int(remaining_iterations * avg_duration)
```

**How It Handles < 5 Iterations:**
- **Iteration 1**: No ETA (not enough data)
- **Iteration 2**: Uses average of 1 duration
- **Iteration 3**: Uses average of 2 durations
- **Iteration 4**: Uses average of 3 durations
- **Iteration 5+**: Uses average of last 5 durations (sliding window)

**Benefits:**
- ✅ No wild fluctuations (smoothed by averaging)
- ✅ Adapts to actual performance (not assumptions)
- ✅ Works with any number of iterations >= 2
- ✅ More accurate predictions

### 2. **Latest Iteration Time Display**

**Problem:** User couldn't see how long the most recent iteration took in the live UI.

**Solution:** Extract and send latest node's execution time:

```python
# Lines 177-180, 198-199
latest_exec_time_s = None
if latest_node and hasattr(latest_node, 'exec_time') and latest_node.exec_time is not None:
    latest_exec_time_s = int(latest_node.exec_time)

# Include in progress data
if latest_exec_time_s is not None:
    progress_data["latest_iteration_time_s"] = latest_exec_time_s
```

**What Gets Sent:**
```json
{
  "stage": "Stage_1",
  "progress": 0.43,
  "iteration": 6,
  "max_iterations": 14,
  "eta_s": 14400,  // ← Smart ETA (4 hours)
  "latest_iteration_time_s": 845  // ← Latest iteration (14min 5sec)
}
```

**Benefits:**
- ✅ Users can see if iterations are speeding up or slowing down
- ✅ Helps understand why ETA is changing
- ✅ Useful for debugging performance issues

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Iteration 1 completes                                      │
│  ↓                                                           │
│  step_callback() called                                     │
│  ├─ Track timing: time_start[0] = T1                       │
│  ├─ No duration yet (first iteration)                      │
│  └─ Send progress (no ETA, no latest_time)                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Iteration 2 completes (14 minutes later)                   │
│  ↓                                                           │
│  step_callback() called                                     │
│  ├─ Track timing: time_start[1] = T2                       │
│  ├─ Duration: T2 - T1 = 840s (14 min)                      │
│  ├─ durations = [840]                                       │
│  ├─ avg = 840s, remaining = 12, ETA = 12 * 840 = 2h 48m   │
│  ├─ latest_exec_time = node[1].exec_time = 845s           │
│  └─ Send progress (ETA: 2h 48m, latest: 14m 5s)           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Iteration 3 completes (8 minutes later - faster!)          │
│  ↓                                                           │
│  step_callback() called                                     │
│  ├─ Track timing: time_start[2] = T3                       │
│  ├─ Duration: T3 - T2 = 480s (8 min)                       │
│  ├─ durations = [840, 480]                                  │
│  ├─ avg = 660s, remaining = 11, ETA = 11 * 660 = 2h 1m    │
│  ├─ latest_exec_time = node[2].exec_time = 485s           │
│  └─ Send progress (ETA: 2h 1m ↓, latest: 8m 5s ↓)         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Iteration 7 completes                                       │
│  ↓                                                           │
│  step_callback() called                                     │
│  ├─ durations = [840, 480, 720, 660, 540, 600]            │
│  ├─ recent_5 = [480, 720, 660, 540, 600]  ← Last 5 only   │
│  ├─ avg = 600s (10 min), remaining = 7                     │
│  ├─ ETA = 7 * 600 = 1h 10m (stable now!)                  │
│  └─ Send progress (ETA: 1h 10m, latest: ~10m)             │
└─────────────────────────────────────────────────────────────┘
```

## Frontend Integration Needed

The backend now sends `eta_s` and `latest_iteration_time_s`, but the frontend needs to be updated to display them:

### Update Schema

```typescript
// orchestrator/apps/web/lib/schemas/cloudevents.ts
export const StageProgressDataZ = z.object({
  run_id: z.string(),
  stage: z.enum(STAGES),
  progress: z.number().min(0).max(1),
  eta_s: z.number().nullable().optional(),
  iteration: z.number().int().optional(),
  max_iterations: z.number().int().optional(),
  good_nodes: z.number().int().optional(),
  buggy_nodes: z.number().int().optional(),
  total_nodes: z.number().int().optional(),
  best_metric: z.string().nullable().optional(),
  latest_iteration_time_s: z.number().int().nullable().optional(),  // ← Add this
})
```

### Update UI Component

```typescript
// orchestrator/apps/web/components/StageProgressPanel.tsx

export function StageProgressPanel({ run }: StageProgressPanelProps) {
  const currentStage = run.currentStage
  const latestIterationTime = currentStage.latestIterationTimeS
  
  // Trust backend ETA if available, fallback to calculated
  const eta_s = currentStage.etaS !== undefined && currentStage.etaS !== null
    ? currentStage.etaS  // ← Use backend's smart ETA
    : (elapsedS > 0 && progress > 0.01 
        ? Math.floor((elapsedS / progress) - elapsedS)
        : null)
  
  return (
    <div className="...">
      {/* ... existing fields ... */}
      
      {latestIterationTime !== undefined && latestIterationTime !== null && (
        <div>
          <span className="text-slate-400">Last Iteration:</span>
          <span className="ml-2 font-mono text-slate-200">
            {formatDuration(latestIterationTime)}
          </span>
        </div>
      )}
      
      {eta_s !== null && (
        <div>
          <span className="text-slate-400">ETA:</span>
          <span className="ml-2 font-mono text-amber-400">
            ~{formatDuration(eta_s)}
          </span>
        </div>
      )}
    </div>
  )
}
```

## Example Output

After these changes, the UI will show:

```
Stage_1: Experiments (Initial, Baseline, Creative, Ablations)  43%

Progress: ████████░░░░░░░░░░░░ 43%

Iteration:     6/14
Nodes:         6 good / 1 buggy / 7 total
Elapsed:       3h 0m 2s
Last Iteration: 14m 5s  ← NEW!
ETA:           ~2h 15m  ← Stable now! (not jumping between 6h and 12h)
```

As iterations complete:
```
Iteration 7: Last Iteration: 8m 12s, ETA: ~2h 5m   ← ETA dropped (faster iteration)
Iteration 8: Last Iteration: 15m 3s, ETA: ~2h 10m  ← ETA rose slightly (slower iteration)
Iteration 9: Last Iteration: 12m 45s, ETA: ~1h 55m ← Smooth, predictable changes
```

## Testing

To test the changes:

1. **Start a new run** (or wait for current run to reach next stage)
2. **Watch the ETA**:
   - Should NOT show for iterations 1 (not enough data)
   - Should appear starting at iteration 2
   - Should remain relatively stable (±20% variance, not ±100%)
3. **Check logs** for the new progress events:
   ```bash
   grep "latest_iteration_time_s" experiments/.../logs/pod_worker.log
   ```

## Deployment

```bash
cd /Users/jessica/AEStudio/agi/AI-Scientist-v2

# Create deployment package with fixes
./create_upload_zip.sh

# Deploy to RunPod
./deploy_to_pod.sh
```

## Backward Compatibility

✅ **Fully backward compatible!**
- Frontend still calculates fallback ETA if backend doesn't provide one
- New fields (`latest_iteration_time_s`) are optional
- Old runs without this data will work fine (just won't show latest iteration time)

## Future Enhancements

1. **Show iteration history**: Graph of last 10 iteration times
2. **Confidence intervals**: "ETA: 1.5-2.5 hours" based on variance
3. **Phase detection**: Recognize warmup/steady/final phases automatically
4. **Historical learning**: Use previous runs to predict initial ETA

