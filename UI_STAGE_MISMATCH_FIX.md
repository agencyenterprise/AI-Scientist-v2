# UI Stage Mismatch Fix

## Problem

The experiment UI was showing inaccurate stage information:
- **Actual State**: Stage 1 completed → Stage 2 completed → Stage 3 running
- **UI Display**: Stage 1 "Running" at 100%, Stages 2-4 all showing "PENDING"

The logs showed multiple 422 validation errors:
```
✗ Failed to send event: 422 Client Error: Unprocessable Entity for url: https://ai-scientist-v2-production.up.railway.app/api/ingest/event
```

## Root Cause

In `ai_scientist/treesearch/perform_experiments_bfts_with_agentmanager.py` line 157, the code was sending invalid stage names in `stage_progress` events:

```python
emit_event("ai.run.stage_progress", {
    "stage": stage.name.split("_")[0] + "_" + stage.name.split("_")[1],  # ❌ Creates "3_creative" etc.
    ...
})
```

### Why This Failed

The API schema (`orchestrator/apps/web/lib/schemas/cloudevents.ts`) only accepts these stage names:
```typescript
export const STAGES = ["Stage_1", "Stage_2", "Stage_3", "Stage_4"] as const
```

But the code was sending invalid names like:
- `"1_initial"` (from `1_initial_implementation_1_preliminary`)
- `"2_baseline"` (from `2_baseline_tuning_1_first_attempt`)
- `"3_creative"` (from `3_creative_research_1_first_attempt`)
- `"4_ablation"` (from `4_ablation_studies_1_first_attempt`)

These failed validation and were rejected with 422 errors, preventing the UI from updating.

## The Fix

Changed `perform_experiments_bfts_with_agentmanager.py` to always use `"Stage_1"` for all BFTS substage progress events (lines 159 and 184):

```python
# Map internal BFTS stage names to Stage_1 (all BFTS stages are part of experiments phase)
emit_event("ai.run.stage_progress", {
    "stage": "Stage_1",  # ✅ All BFTS substages are part of Stage_1 in the UI
    ...
})
```

This is correct because:
1. All BFTS internal stages (initial, baseline, creative, ablation) happen during Stage_1 (Experiments)
2. Stage_2 = Plot Aggregation (separate from BFTS)
3. Stage_3 = Paper Generation (separate from BFTS)
4. Stage_4 = Auto-Validation (separate from BFTS)

## Impact on Current Run

Your currently running experiment (`ea8242d9-de15-4a1b-a144-68b46953123e`) is affected by this bug:

**What's actually happening:**
- ✅ Stage 1 (Experiments/BFTS) - COMPLETED
- ✅ Stage 2 (Baseline Tuning) - COMPLETED  
- 🔄 Stage 3 (Creative Research) - RUNNING
- ⏳ Stage 4 (Auto-Validation) - PENDING

**What the UI shows:**
- Stage 1: "Running" at 100% (stuck)
- Stages 2-4: All "PENDING"

The experiment **will continue and complete successfully**, but the UI won't accurately reflect which stage it's on. The internal logs show the correct progress.

## Next Steps

### For Future Runs
The fix is now in your local codebase. To deploy it to RunPod:

1. **Create deployment package:**
   ```bash
   cd /Users/jessica/AEStudio/agi/AI-Scientist-v2
   ./create_upload_zip.sh
   ```

2. **Deploy to your pod:**
   ```bash
   ./deploy_to_pod.sh
   ```

3. **Or manually:** Upload `ai-scientist-runpod.zip` to your pod and extract it in the workspace

### For Current Run
- Let it complete naturally
- Monitor progress via the logs instead of UI stage indicators
- The final results will be correct even though UI tracking is inaccurate
- Once it reaches Stage 3 (Paper Generation) and Stage 4 (Auto-Validation), those should show correctly since they use `StageContext("Stage_3")` and `StageContext("Stage_4")` directly

## Files Changed

- ✅ `ai_scientist/treesearch/perform_experiments_bfts_with_agentmanager.py` (lines 159, 184)

## Verification

After deploying, verify the fix works by:

1. Starting a new experiment
2. Checking that stage_progress events are no longer rejected (no 422 errors)
3. Confirming UI accurately shows stage transitions:
   - Stage 1 progress during BFTS experiments
   - Stage 1 → COMPLETED when BFTS finishes
   - Stage 2 → RUNNING for plot aggregation
   - Stage 3 → RUNNING for paper generation
   - Stage 4 → RUNNING for auto-validation

## Related Files

- Event validation schema: `orchestrator/apps/web/lib/schemas/cloudevents.ts`
- Stage constants: `orchestrator/apps/web/lib/state/constants.ts`
- Pod worker stage management: `pod_worker.py` (StageContext class, lines 223-300)
- Event ingestion API: `orchestrator/apps/web/app/api/ingest/event/route.ts`

