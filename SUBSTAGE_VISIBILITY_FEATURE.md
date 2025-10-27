# Substage Visibility Feature

## Problem
Users were staring at "Stage 1: Preliminary Investigation - RUNNING" for hours with no visibility into what was actually happening. Stage 1 contains ALL 4 internal Sakana stages:
1. Initial Implementation
2. Baseline Tuning  
3. Creative Research
4. **Ablation Studies**

## Solution
Added substage visibility without modifying the Sakana pipeline.

## Changes Made

### 1. Backend (`pod_worker.py`)
- Modified `experiment_event_callback` to store substage information
- Now stores `currentStage.substage` and `currentStage.substageFull` in MongoDB
- Keeps main stage as `Stage_1` (UI compatible) while showing internal Sakana progress

### 2. Schema (`orchestrator/apps/web/lib/schemas/run.ts`)
- Added `substage?: string` field to currentStage schema
- Added `substageFull?: string` field for detailed display

### 3. UI Components

**StageProgress.tsx**
- Added substage display under running stages
- Shows as `→ Creative Research (5/8 nodes)` in sky-blue color

**RunDetailClient.tsx**
- Updated `toStageProgress()` to pass substage info from currentStage
- Substage only shown when that stage is actively RUNNING

## Result
Users can now see real-time progress through internal Sakana stages:
- **Stage 1** (Preliminary Investigation)
  - → Initial Implementation (3/16 nodes)
  - → Baseline Tuning (7/10 nodes)
  - → Creative Research (2/8 nodes)
  - → **Ablation Studies (9/14 nodes)** ← Now visible!

## How It Works
1. Sakana pipeline emits `ai.run.stage_progress` events with internal stage names
2. pod_worker captures these and stores as substage in MongoDB
3. UI displays substage under Stage 1 when running
4. Progress bar shows actual progress through internal stages

## No Sakana Changes Required
✅ All changes in wrapper layer (pod_worker + UI)
✅ Sakana pipeline untouched
✅ Backward compatible with existing runs

