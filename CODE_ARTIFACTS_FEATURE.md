# Code Artifacts Feature

## Summary
Added automatic upload of best experimental code as downloadable artifacts after each run completes.

## What Gets Uploaded

### Code Files (up to 4 files)
1. **`best_code_stage_1.py`** - Initial Implementation
   - First working version of the idea
   - Basic functional correctness

2. **`best_code_stage_2.py`** - Baseline Tuning
   - Hyperparameter-tuned baseline
   - Optimized learning rates, batch sizes, etc.

3. **`best_code_stage_3.py`** - Creative Research ⭐
   - **Main results used in the paper**
   - Novel improvements and experiments
   - Best performing implementation

4. **`best_code_stage_4.py`** - Ablation Studies
   - Component analysis variations
   - Tests different aspects of the model

### Documentation
- **`BEST_SOLUTIONS_README.md`** - Explains each code file
  - Which stage it's from
  - Node ID for traceability
  - How to reproduce results
  - Selection process details

## Where Code Comes From

```
experiments/<experiment_name>/
├── logs/
│   └── 0-run/
│       ├── stage_1_initial_implementation_1_first_attempt/
│       │   └── best_solution_<node_id>.py  ← Source
│       ├── stage_2_baseline_tuning_1_first_attempt/
│       │   └── best_solution_<node_id>.py  ← Source
│       ├── stage_3_creative_research_1_first_attempt/
│       │   └── best_solution_<node_id>.py  ← Source (⭐ Main)
│       └── stage_4_ablation_studies_1_first_attempt/
│           └── best_solution_<node_id>.py  ← Source
│
└── [After copy_best_solutions_to_root()]:
    ├── best_code_stage_1.py  ← Uploaded
    ├── best_code_stage_2.py  ← Uploaded
    ├── best_code_stage_3.py  ← Uploaded (⭐ Use this one!)
    ├── best_code_stage_4.py  ← Uploaded
    └── BEST_SOLUTIONS_README.md  ← Uploaded
```

## Implementation Details

### Timing
Code artifacts are uploaded **after all experiments complete**, right after:
1. All 4 Sakana stages finish (Initial, Baseline, Creative, Ablations)
2. All stage PDFs are generated
3. `copy_best_solutions_to_root()` copies best code to root
4. **→ Code artifacts uploaded here** ← NEW!
5. Archive created and uploaded to MinIO

### Code Location (pod_worker.py)
```python
# Lines 1127-1169
# After copy_best_solutions_to_root(idea_dir)

# Upload best code files as artifacts
print(f"\n📦 Uploading best code artifacts...")
code_files_uploaded = 0
for stage_num in range(1, 5):  # Stages 1-4
    code_file = f"best_code_stage_{stage_num}.py"
    code_path = os.path.join(idea_dir, code_file)
    
    if os.path.exists(code_path):
        upload_result = upload_artifact(run_id, code_path, "code")
        # ... logging ...
```

### Artifact Types
- **Code files**: `kind="code"`
- **README**: `kind="documentation"`

### Error Handling
- Skips gracefully if stage didn't complete (no file exists)
- Logs warnings if upload fails but continues
- Shows status for each file in logs

## UI Display

Users will see in the Artifacts section:
```
Artifacts (7 items)

Code
├─ best_code_stage_1.py (15.2 KB) [DOWNLOAD]
├─ best_code_stage_2.py (16.8 KB) [DOWNLOAD]
├─ best_code_stage_3.py (18.4 KB) [DOWNLOAD]  ⭐ Main results
└─ best_code_stage_4.py (17.1 KB) [DOWNLOAD]

Documentation
└─ BEST_SOLUTIONS_README.md (3.2 KB) [DOWNLOAD]

Paper
├─ reflection1.pdf (1.2 MB) [DOWNLOAD]
└─ reflection_final.pdf (1.9 MB) [DOWNLOAD]
```

## Benefits

✅ **Easy Reproducibility**: Download and run the exact code that produced results
✅ **Version Tracking**: Each stage's best code is preserved
✅ **Traceability**: README links code to node IDs in journals
✅ **Publication Ready**: Can include code with paper submissions
✅ **Debugging**: See what worked in each stage
✅ **Comparison**: Compare implementations across stages

## Example Usage

After download:
```bash
# Download best_code_stage_3.py from UI

# Run to reproduce main results
python best_code_stage_3.py

# Output: Same results as reported in the paper
```

## Logging Examples

### Console Output
```
📋 Copying best solutions to experiment root...
✓ Copied best_code_stage_1.py (node: a1b2c3d4...)
✓ Copied best_code_stage_2.py (node: e5f6g7h8...)
✓ Copied best_code_stage_3.py (node: i9j0k1l2...)
✓ Copied best_code_stage_4.py (node: m3n4o5p6...)
✓ Created BEST_SOLUTIONS_README.md
✓ Copied 4 best solution file(s) to experiment root

📦 Uploading best code artifacts...
   Uploading best_code_stage_1.py...
   ✓ best_code_stage_1.py uploaded
   Uploading best_code_stage_2.py...
   ✓ best_code_stage_2.py uploaded
   Uploading best_code_stage_3.py...
   ✓ best_code_stage_3.py uploaded
   Uploading best_code_stage_4.py...
   ✓ best_code_stage_4.py uploaded
✓ Uploaded 4 code artifact(s)

📄 Uploading code documentation...
   ✓ BEST_SOLUTIONS_README.md uploaded
```

### Live Logs in UI
```
[INFO] Code artifact uploaded: best_code_stage_1.py
[INFO] Code artifact uploaded: best_code_stage_2.py
[INFO] Code artifact uploaded: best_code_stage_3.py
[INFO] Code artifact uploaded: best_code_stage_4.py
[INFO] Uploaded 4 code artifacts
[INFO] Code documentation uploaded
```

## Notes

- Only stages that completed successfully will have code files
- If an experiment fails at Stage 2, only `best_code_stage_1.py` will be uploaded
- Stage 3 code is typically the most important (used in paper)
- Each file is standalone and can be run independently

