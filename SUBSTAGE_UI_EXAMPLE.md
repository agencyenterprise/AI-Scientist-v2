# Substage Visibility - UI Example

## Before (Confusing)
```
Pipeline Stages
───────────────
Stage 1
Preliminary Investigation                                RUNNING
[████████████████░░░░░░░░░░░░░░] 55%

Stage 2  
Baseline Tuning                                          PENDING
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0%

Stage 3
Research Agenda Execution                                PENDING
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0%

Stage 4
Ablation Studies                                         PENDING
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0%
```
❌ Users don't know what's happening for hours!

## After (Clear!)
```
Pipeline Stages
───────────────
Stage 1
Experiments (Initial, Baseline, Creative, Ablations)     RUNNING
→ Ablation Studies (9/14 nodes)
[████████████████████░░░░░░░░░░] 64%

Stage 2
Plot Aggregation                                         PENDING
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0%

Stage 3
Paper Generation                                         PENDING
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0%

Stage 4
Auto-Validation                                          PENDING
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0%
```
✅ Users can see it's running ablation studies!

## What Users See During Stage 1

### First Hour
```
Stage 1
Experiments (Initial, Baseline, Creative, Ablations)     RUNNING
→ Initial Implementation (3/16 nodes)
[███░░░░░░░░░░░░░░░░░░░░░░░░░░] 19%
```

### Second Hour
```
Stage 1
Experiments (Initial, Baseline, Creative, Ablations)     RUNNING
→ Baseline Tuning (7/10 nodes)
[████████████░░░░░░░░░░░░░░░░░] 70%
```

### Third Hour
```
Stage 1
Experiments (Initial, Baseline, Creative, Ablations)     RUNNING
→ Creative Research (2/8 nodes)
[███████░░░░░░░░░░░░░░░░░░░░░░] 25%
```

### Fourth Hour
```
Stage 1
Experiments (Initial, Baseline, Creative, Ablations)     RUNNING
→ Ablation Studies (11/14 nodes)
[██████████████████████░░░░░░░] 79%
```

## Technical Details

- **Substage updates every ~30 seconds** (when each node completes)
- **Shows node progress**: `(good_nodes/total_nodes)`
- **Sky blue color** (text-sky-400) for visibility
- **Only shows when RUNNING** (disappears when complete)

## All Stages Explained

| Stage | What It Actually Does | Duration |
|-------|----------------------|----------|
| Stage 1 | Runs 4 internal Sakana stages (experiments) | 2-4 hours |
| Stage 2 | Aggregates plots from all experiments | 5-10 min |
| Stage 3 | Generates paper with citations | 15-30 min |
| Stage 4 | LLM reviews paper and scores it | 5-10 min |

## Key Insight for Users

**Stage 1 contains ALL the experimental work**, including the ablation studies you were asking about!

The experiments ARE testing dropout, attention, different datasets, etc. - you just couldn't see it before.

