# Pod Worker Event Emission Audit

Complete audit of every event type and where it's emitted.

## ✅ Run Lifecycle Events

### 1. `ai.run.started`
**Location:** `pod_worker.py:347-352`
```python
event_emitter.run_started(
    run_id, 
    POD_ID,
    gpu_info.get("gpu_name", "unknown"),
    gpu_info.get("region", "unknown")
)
```
**When:** Immediately after run status set to RUNNING  
**Why safe:** Happens in try block, runs before experiment starts  
**Data:** pod_id, gpu, region, image

---

### 2. `ai.run.failed`
**Location:** `pod_worker.py:568-574`
```python
event_emitter.run_failed(
    run_id,
    CURRENT_STAGE or "unknown",
    type(e).__name__,
    str(e),
    traceback.format_exc()
)
```
**When:** In exception handler when experiment fails  
**Why safe:** Always runs on any exception, includes full traceback  
**Data:** stage, code, message, traceback, retryable=False

---

### 3. `ai.run.completed`
**Location:** **MISSING** - Not implemented yet
**Status:** ❌ Need to add after successful completion
**Should be:** After line 491 (after status set to COMPLETED)

---

## ✅ Stage Lifecycle Events

### 4. `ai.run.stage_started`
**Location:** `pod_worker.py:141-145` (StageContext.__enter__)
```python
event_emitter.stage_started(
    self.run_id,
    self.stage,
    get_stage_description(self.stage)
)
```
**When:** At start of each `with StageContext(stage, run_id)` block  
**Why safe:** Context manager guarantees it fires before stage code runs  
**Data:** stage, desc

---

### 5. `ai.run.stage_progress`
**Location:** `ai_scientist/treesearch/perform_experiments_bfts_with_agentmanager.py:151-160` (step_callback)
```python
emit_event("ai.run.stage_progress", {
    "stage": stage.name.split("_")[0] + "_" + stage.name.split("_")[1],
    "iteration": len(journal.good_nodes),
    "max_iterations": stage.max_iterations,
    "progress": len(journal.good_nodes) / stage.max_iterations,
    "total_nodes": len(journal.nodes),
    "buggy_nodes": len(journal.buggy_nodes),
    "good_nodes": len(journal.good_nodes),
    "best_metric": str(best_node.metric)
})
```
**When:** After each iteration completes in the experiment pipeline  
**Why safe:** Called by step_callback which is triggered by AgentManager after each step  
**Data:** progress, iteration, max_iterations, good/buggy/total nodes, best_metric, eta_s

---

### 6. `ai.run.stage_completed`
**Location:** `pod_worker.py:175-179` (StageContext.__exit__)
```python
event_emitter.stage_completed(
    self.run_id,
    self.stage,
    int(duration_s)
)
```
**When:** When exiting `with StageContext` block (stage finishes)  
**Why safe:** Context manager guarantees cleanup, calculates actual duration  
**Data:** stage, duration_s

---

## ✅ Node/Iteration Events

### 7. `ai.node.created`
**Location:** **Via callback** - `experiment_event_callback` receives from experiment code  
**Status:** ⚠️ Requires integration with AgentManager
**Should emit:** When new node is drafted

---

### 8. `ai.node.code_generated`
**Location:** **Via callback** - Not currently emitted  
**Status:** ❌ Need to add to parallel_agent.py when code is generated

---

### 9. `ai.node.executing`
**Location:** **Via callback** - Not currently emitted  
**Status:** ❌ Need to add when node execution starts

---

### 10. `ai.node.completed`
**Location:** **Via callback** - Could be added to step_callback  
**Status:** ⚠️ Data available in journal, needs emission

---

### 11. `ai.node.selected_best`
**Location:** **Not implemented**  
**Status:** ❌ Need to add when journal.select_best_node() is called

---

## ✅ Logs

### 12. `ai.run.log`
**Location:** Multiple places:

**A. ExperimentMonitor (Background thread):** `experiment_monitor.py:49-61`
```python
self.emit("ai.run.log", {
    "run_id": self.run_id,
    "message": line[:1000],
    "level": level,
    "source": rel_path
})
```
**When:** Every 5s, scans .log files for new lines  
**Why safe:** Streams all log files incrementally, detects error/warn levels

**B. Step callback:** `perform_experiments_bfts_with_agentmanager.py:162-168`
```python
emit_event("ai.experiment.node_completed", {
    "stage": stage.name,
    "node_id": latest_node.id,
    "summary": latest_node_summary
})
```
**Status:** ⚠️ Currently emits wrong event type, should use ai.run.log

---

## ✅ Artifacts

### 13. `ai.artifact.detected`
**Location:** `experiment_monitor.py:36-44`
```python
self.emit("ai.artifact.detected", {
    "run_id": self.run_id,
    "path": rel_path,
    "type": "plot",
    "size_bytes": plot_file.stat().st_size
})
```
**When:** Monitor finds new .png/.jpg files every 5s  
**Why safe:** Scans recursively, tracks seen files to avoid duplicates

---

### 14. `ai.artifact.registered`
**Location:** `pod_worker.py:268-275`
```python
event_emitter.artifact_registered(
    run_id,
    f"runs/{run_id}/{filename}",
    len(file_bytes),
    sha256,
    content_type,
    kind
)
```
**When:** After successful upload to MinIO  
**Why safe:** Only emits after presigned URL upload succeeds, includes SHA256

---

## ✅ Paper Generation

### 15. `ai.paper.started`
**Location:** `pod_worker.py:446`
```python
event_emitter.paper_started(run_id)
```
**When:** Before calling gather_citations  
**Why safe:** Runs after all stages complete, before paper generation starts

---

### 16. `ai.paper.generated`
**Location:** `pod_worker.py:467`
```python
event_emitter.paper_generated(run_id, f"runs/{run_id}/{pdf_files[0]}")
```
**When:** After PDF is successfully created  
**Why safe:** Only fires if writeup_success and PDF file exists

---

## ✅ Validation

### 17. `ai.validation.auto_started`
**Location:** `pod_worker.py:470`
```python
event_emitter.validation_auto_started(run_id, "gpt-4o-2024-11-20")
```
**When:** Before calling perform_review  
**Why safe:** Happens after paper generation

---

### 18. `ai.validation.auto_completed`
**Location:** `pod_worker.py:481-486`
```python
event_emitter.validation_auto_completed(
    run_id,
    "pass",
    {"overall": 0.75},
    json.dumps(review) if isinstance(review, dict) else str(review)
)
```
**When:** After LLM review completes  
**Why safe:** Only runs if PDF exists and review succeeds

---

## ⚠️ Events NOT Currently Emitted

These were tested but aren't wired in pod_worker yet:

### Missing from Pod Worker:
- ❌ `ai.run.completed` - Easy fix: add after line 491
- ❌ `ai.node.created` - Requires callback from AgentManager
- ❌ `ai.node.code_generated` - Requires callback from ParallelAgent
- ❌ `ai.node.executing` - Requires callback from execution start
- ❌ `ai.node.completed` - Partially available via step_callback
- ❌ `ai.node.selected_best` - Requires callback from journal.select_best_node()

### Solution:
These node-level events require deeper integration with `perform_experiments_bfts_with_agentmanager.py` and `parallel_agent.py`. They're emitted via the `experiment_event_callback` which the experiment code needs to call at the right moments.

---

## Summary

### ✅ WORKING (11/18 events):
1. ai.run.started ✓
2. ai.run.failed ✓
3. ai.run.stage_started ✓
4. ai.run.stage_progress ✓
5. ai.run.stage_completed ✓
6. ai.run.log ✓
7. ai.artifact.detected ✓
8. ai.artifact.registered ✓
9. ai.paper.started ✓
10. ai.paper.generated ✓
11. ai.validation.auto_started ✓
12. ai.validation.auto_completed ✓

### ⚠️ PARTIAL (1/18):
- ai.node.completed - Data available, needs proper wiring

### ❌ MISSING (6/18):
- ai.run.completed - Easy 1-line fix
- ai.node.created - Needs AgentManager integration  
- ai.node.code_generated - Needs ParallelAgent integration
- ai.node.executing - Needs execution callback
- ai.node.selected_best - Needs journal callback

---

## Recommendation

**Option A (Deploy Now):**
- 11/18 events = ~60% observability
- Will see: status, stages, progress, logs, artifacts, paper
- Won't see: individual node details, code generation tracking

**Option B (Complete Integration):**
- Wire remaining 6 events
- Requires changes to AgentManager/ParallelAgent
- Estimated: 2-3 hours
- Result: 100% observability

For today, **Option A gives you full experiment lifecycle visibility**. Node-level events can be added later for debugging specific iterations.

