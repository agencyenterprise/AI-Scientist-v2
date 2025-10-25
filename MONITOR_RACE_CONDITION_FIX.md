# Monitor Race Condition Fix

## Problem

During experiments, you saw errors like:
```
Monitor error: [Errno 2] No such file or directory: 
'experiments/.../0-run/process_SpawnProcess-14/working/high_noise_baseline_closed_correctness_timeline.png'
```

## Root Cause

**Race Condition Between File Detection and File Access**

The system has two concurrent processes handling plots:

1. **Experiment Execution** (`parallel_agent.py`):
   - Generates plots in temporary `working` directory
   - Moves them to `logs/0-run/experiment_results/`

2. **File Monitor** (`experiment_monitor.py`):
   - Scans for plots using glob patterns
   - Tries to get file size with `stat()`
   - Attempts to upload plots

### The Race:
```
Time 0: Plot created in working/plot.png
Time 1: Monitor detects it via glob
Time 2: parallel_agent moves it to logs/experiment_results/plot.png  
Time 3: Monitor tries stat() on working/plot.png → FILE NOT FOUND ❌
```

## The Fix

### 1. **Graceful Error Handling in `experiment_monitor.py`**

Added try-catch around file operations that might fail if files are moved:

```python
# Get file size safely - file might be moved by parallel agent
try:
    size_bytes = plot_file.stat().st_size
except (FileNotFoundError, OSError):
    # File was moved between glob and stat - skip for now, 
    # will catch it in new location on next scan
    self.uploaded_plots.remove(rel_path)
    continue
```

This applies to:
- ✅ Plot detection (`_check_plots()`)
- ✅ Checkpoint detection (`_check_checkpoints()`)

### 2. **Better Error Reporting in `pod_worker.py`**

Added traceback printing for monitor errors:

```python
except Exception as e:
    print(f"Monitor error: {e}")
    import traceback
    traceback.print_exc()
```

Also made the iteration safer by copying the set to a list first to avoid modification during iteration.

## Result

### Before:
- ❌ Errors printed for every moved file
- ❌ Monitor couldn't handle files being relocated
- ❌ Race conditions caused failures

### After:
- ✅ Gracefully handles moved files
- ✅ Catches files in new location on next scan
- ✅ No more "file not found" errors
- ✅ Better debugging with full tracebacks

## Other Issues in the Log

### 1. Too Many Plots (52 plots)
```
Warning: 52 plots received, this may be too many to analyze effectively.
```
This is **expected behavior** - the system uses an LLM to filter down to most relevant plots. Not an error.

### 2. HTTP Timeout
```
✗ Failed to send events: HTTPSConnectionPool(...): Read timed out.
```
This is a **network issue** between the worker and Railway. The experiment continues running, just the live updates to the web UI fail temporarily. This is non-fatal.

## Files Modified

- `experiment_monitor.py`: Added error handling for file operations
- `pod_worker.py`: Improved error reporting and iteration safety

## Testing

The fix is defensive and will:
1. Catch the file in its new location on the next scan (5 seconds later)
2. Not break if files are moved, deleted, or renamed
3. Continue monitoring without crashes

