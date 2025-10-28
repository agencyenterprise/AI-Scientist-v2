# ETA Calculation Improvement Proposal

## Current Problems

1. **Wild fluctuations**: ETA swings between 6h and 12h as iterations vary in duration
2. **Inaccurate**: Finished much faster than predicted
3. **Naive algorithm**: Simple linear extrapolation assumes constant velocity
4. **Cold start bias**: Early slow iterations skew the entire prediction

## Current Implementation

```typescript
// StageProgressPanel.tsx lines 53-55
const eta_s = elapsedS > 0 && progress > 0.01 
  ? Math.floor((elapsedS / progress) - elapsedS)  // ❌ Assumes constant velocity
  : null
```

**Formula**: `ETA = (elapsed / progress) - elapsed`

**Example of the problem**:
- Iteration 1: 10 min → ETA predicts 140 min total
- Iteration 2: 30 min → ETA jumps to 300 min total! 📈
- Iteration 3: 8 min → ETA drops to 150 min 📉
- User sees: 2h 20m → 5h → 2h 30m (confusing!)

## Proposed Solution: Moving Average with Exponential Smoothing

### Architecture Changes

**Backend** (`perform_experiments_bfts_with_agentmanager.py`):
Track iteration timing history and send it in progress events.

```python
# Add to step_callback function
iteration_start_times = []  # Store in closure or class
iteration_durations = []    # Store in closure or class

def step_callback(stage, journal):
    current_time = time.time()
    
    # Track iteration duration
    if len(iteration_start_times) > 0:
        duration = current_time - iteration_start_times[-1]
        iteration_durations.append(duration)
    
    iteration_start_times.append(current_time)
    
    # Calculate smart ETA using moving average
    if len(iteration_durations) >= 3:
        # Use exponential weighted moving average
        recent_durations = iteration_durations[-5:]  # Last 5 iterations
        avg_duration = sum(recent_durations) / len(recent_durations)
        
        remaining_iterations = stage.max_iterations - len(journal.nodes)
        eta_s = int(remaining_iterations * avg_duration)
    else:
        # Fallback for first few iterations
        eta_s = None
    
    emit_event("ai.run.stage_progress", {
        "stage": "Stage_1",
        "progress": progress,
        "iteration": current_iteration,
        "max_iterations": stage.max_iterations,
        "eta_s": eta_s,  # Send smarter ETA from backend
        # ... other fields ...
    })
```

**Frontend** (`StageProgressPanel.tsx`):
Use backend-provided ETA when available, with fallback.

```typescript
// Option 1: Trust backend ETA (recommended)
const eta_s = currentStage.eta_s !== undefined && currentStage.eta_s !== null
  ? currentStage.eta_s
  : null  // Don't show ETA if backend hasn't calculated it yet

// Option 2: Keep fallback but make it smarter
const fallbackEta = elapsedS > 0 && progress > 0.01 
  ? Math.floor((elapsedS / progress) - elapsedS)
  : null

const eta_s = currentStage.eta_s !== undefined && currentStage.eta_s !== null
  ? currentStage.eta_s
  : fallbackEta
```

### Benefits

1. **Stable**: Averages out variation across iterations
2. **Adaptive**: Responds to actual performance, not assumptions
3. **Accurate**: Learns from recent history
4. **No cold-start bias**: Only starts predicting after 3 iterations

### Advanced: Phase-Aware ETA

For even better accuracy, recognize iteration phases:

```python
def calculate_phase_aware_eta(iteration_durations, current_iteration, max_iterations):
    """
    Recognize that early iterations are slower (cold start),
    middle iterations are fastest (steady state),
    and final iterations may be slower (wrap-up).
    """
    n = len(iteration_durations)
    
    if n < 3:
        return None  # Not enough data
    
    # Categorize iterations into phases
    warmup_phase = iteration_durations[:min(3, n)]
    steady_phase = iteration_durations[3:] if n > 3 else []
    
    # Use steady-state average if available, otherwise warmup average
    if len(steady_phase) >= 2:
        avg_time = sum(steady_phase) / len(steady_phase)
    else:
        avg_time = sum(warmup_phase) / len(warmup_phase)
    
    remaining = max_iterations - current_iteration
    
    # Apply phase-based adjustment
    if current_iteration < 3:
        # Still in warmup, use warmup average
        eta_s = remaining * avg_time
    else:
        # In steady state, use steady average
        eta_s = remaining * avg_time
    
    return int(eta_s)
```

## Implementation Plan

### Phase 1: Backend Moving Average (2 hours)
- [ ] Add iteration timing tracking to `perform_experiments_bfts_with_agentmanager.py`
- [ ] Calculate moving average ETA in `step_callback`
- [ ] Send calculated ETA in progress events
- [ ] Test with mock data

### Phase 2: Frontend Trust Backend (30 minutes)
- [ ] Update `StageProgressPanel.tsx` to prefer backend ETA
- [ ] Add fallback for backward compatibility
- [ ] Test with real runs

### Phase 3: Advanced Phase-Aware (optional, 3 hours)
- [ ] Implement phase detection
- [ ] Track historical run data for better initial estimates
- [ ] Add confidence intervals (e.g., "2-3 hours remaining")

## Example Output Comparison

### Current (Linear Extrapolation)
```
Iteration 1: ETA 2h 20m
Iteration 2: ETA 5h 0m   📈 (scary!)
Iteration 3: ETA 2h 30m  📉 (confusing!)
Iteration 4: ETA 3h 15m  📈
```

### Proposed (Moving Average)
```
Iteration 1: ETA calculating...
Iteration 2: ETA calculating...
Iteration 3: ETA 2h 45m
Iteration 4: ETA 2h 40m  (stable)
Iteration 5: ETA 2h 35m  (smooth decrease)
```

## Testing

Create a test script that simulates variable iteration times:

```python
# test_eta_calculation.py
import random

def simulate_iterations(n=14):
    """Simulate realistic iteration durations"""
    durations = []
    
    # Cold start (slower)
    for i in range(3):
        durations.append(random.uniform(15*60, 25*60))  # 15-25 min
    
    # Steady state (faster)
    for i in range(3, 11):
        durations.append(random.uniform(8*60, 15*60))   # 8-15 min
    
    # Final (variable)
    for i in range(11, n):
        durations.append(random.uniform(10*60, 18*60))  # 10-18 min
    
    return durations

def test_eta_algorithms():
    durations = simulate_iterations()
    
    # Test current algorithm
    print("Linear Extrapolation ETAs:")
    for i in range(1, len(durations)+1):
        elapsed = sum(durations[:i])
        progress = i / len(durations)
        eta = (elapsed / progress) - elapsed
        print(f"  After iteration {i}: {eta/60:.1f} minutes")
    
    # Test moving average
    print("\nMoving Average ETAs:")
    for i in range(1, len(durations)+1):
        if i >= 3:
            avg = sum(durations[max(0,i-5):i]) / min(i, 5)
            remaining = len(durations) - i
            eta = remaining * avg
            print(f"  After iteration {i}: {eta/60:.1f} minutes")
        else:
            print(f"  After iteration {i}: calculating...")

if __name__ == "__main__":
    test_eta_algorithms()
```

## Rollout

1. **Deploy backend changes first** (backward compatible)
2. **Monitor**: Backend sends ETA, but frontend still calculates fallback
3. **Deploy frontend**: Use backend ETA when available
4. **Observe**: Compare predictions vs. actual for several runs
5. **Tune**: Adjust moving average window size based on data

## Future Enhancements

- **Confidence intervals**: "1.5-2.5 hours remaining" instead of "2 hours"
- **Historical learning**: Use past runs to predict initial ETA
- **Multi-stage total ETA**: Show "Stage 1: 2h, Stages 2-4: 20m, Total: 2h 20m"
- **Pause detection**: Don't count time when no progress is being made

