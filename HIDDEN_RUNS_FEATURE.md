# Hidden Runs Feature

## Overview
Added the ability to hide runs from the dashboard by setting a `hidden: true` field. This allows you to clean up the UI without permanently deleting data from the database.

## Changes Made

### 1. Database Schema
- Added `hidden` field to the Run schema (`orchestrator/apps/web/lib/schemas/run.ts`)
- This field is optional and defaults to not hidden

### 2. Backend Changes

#### Updated Repository Functions (`orchestrator/apps/web/lib/repos/runs.repo.ts`)
- `listRuns()` - Filters out hidden runs by default (`hidden: { $ne: true }`)
- `countRunsByStatus()` - Excludes hidden runs from status counts
- `getHypothesisActivity()` - Excludes hidden runs from activity calculations

#### New API Endpoint (`orchestrator/apps/web/app/api/runs/[id]/hide/route.ts`)
- `POST /api/runs/{id}/hide` - Hides a run (sets `hidden: true`)
- `DELETE /api/runs/{id}/hide` - Unhides a run (sets `hidden: false`)

### 3. Frontend Changes

#### RunTable Component (`orchestrator/apps/web/components/RunTable.tsx`)
- Added "Hide" button next to "View" in the actions column
- Clicking "Hide" calls the API and refreshes the page
- Button shows "Hiding..." state while processing
- Disabled state prevents duplicate clicks

### 4. Python Management Script (`hide_runs.py`)
Command-line utility for managing hidden runs:

```bash
# Hide the predefined runs (those you specified)
python hide_runs.py --hide

# List all hidden runs
python hide_runs.py --list

# Unhide a specific run
python hide_runs.py --unhide <run_id>
```

## Already Hidden Runs
The following 4 runs have been hidden from the dashboard:

1. `f7f195a5-a395-434f-a371-b8772b5683c3` - Observability Test (SCHEDULED)
2. `cbaf7ba6-44fe-413f-a244-640f224ab9fc` - Integration Test (AWAITING_HUMAN)
3. `349fca1e-1e8c-4992-8fc3-f38c644c0aee` - Crystal LLMs (FAILED, Stage 4)
4. `1c7e3b0e-1811-4451-a424-ad68b7d3e591` - Crystal LLMs (FAILED, Stage 1)

## Usage

### From the UI
1. Navigate to the Runs page
2. Find the run you want to hide
3. Click the "Hide" button next to "View"
4. The page will refresh and the run will no longer appear

### From the Command Line
```bash
# Load environment
source .venv/bin/activate
export $(cat .env | grep -v '^#' | xargs)

# Hide specific runs
python hide_runs.py --hide

# Check what's hidden
python hide_runs.py --list

# Unhide if needed
python hide_runs.py --unhide <run_id>
```

## Notes
- Hidden runs are NOT deleted - they remain in the database
- Hidden runs are excluded from:
  - Run listings
  - Status counts
  - Hypothesis activity calculations
- You can unhide runs at any time using the script or by setting `hidden: false` directly in MongoDB
- The `hidden` field is optional, so existing runs without this field will behave as if `hidden: false`

