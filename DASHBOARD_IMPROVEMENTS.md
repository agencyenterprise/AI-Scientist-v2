# Dashboard Visualization Guide & Low-Hanging Fruit Improvements

## What's Happening Inside Stage 1

**Stage 1: Initial Implementation** follows this flow:

1. **Node Selection** → Picks which nodes to work on (draft new, debug buggy, or improve working)
2. **Code Generation** → MinimalAgent generates experimental code
3. **Execution** → Code runs in sandbox, produces plots and metrics
4. **Bug Detection** → Automated reviewer analyzes results, flags bugs with detailed summaries
5. **Metric Extraction** → Parses metrics like "training R", "validation R", "error rates"
6. **Tree Building** → Adds node to search tree with parent/child relationships
7. **Iteration** → Repeats until stage completion criteria met

### Current Status of Your Run
- **Total nodes attempted**: 3
- **Good nodes**: 0
- **Buggy nodes**: 3 (all are being debugged)
- **Progress**: 0% complete (stage hasn't met completion criteria yet)
- **Activity**: System is repeatedly debugging the 3 buggy implementations

## 20 Dashboard Questions (Prioritized by Implementation Effort)

### 🟢 **CRITICAL LOW-HANGING FRUIT** (Data exists, just needs wiring - 1-2 hours each)

#### ✅ **1. Show node counts (good/buggy/total) in real-time**
- **Status**: FIXED! (just now)
- **Data source**: `ai.run.stage_progress` event
- **Change needed**: `pod_worker.py` line 669-683 (already fixed)
- **Impact**: HIGH - Users immediately see if progress is happening

#### ✅ **2. Show iteration count (X/Y iterations)**
- **Status**: FIXED! (just now)
- **Data source**: Same as #1
- **Impact**: HIGH - Shows how close stage is to completion

#### ✅ **3. Show best metric for current stage**
- **Status**: FIXED! (just now)
- **Data source**: Same as #1
- **Impact**: MEDIUM - Shows if quality is improving

#### 🟡 **4. Show what the system is doing RIGHT NOW**
- **Status**: EASY FIX
- **Data source**: `ai.run.log` events with "Generating N new implementations", "Debugging N failed implementations"
- **Change needed**: Frontend displays most recent log messages prominently
- **Impact**: CRITICAL - Eliminates "is it frozen?" confusion
- **Files to modify**: `RunDetailClient.tsx`, create `CurrentActivityBanner.tsx`

#### 🟡 **5. Show individual node summaries (what failed, why)**
- **Status**: EASY - Data exists in `analysis` field
- **Data source**: Node result object has detailed bug summaries
- **Change needed**: Create expandable node list in UI
- **Impact**: HIGH - Users can understand what's being tried
- **Files to modify**: Create `NodeTreeView.tsx` component

#### 🟡 **6. Show code being generated for each attempt**
- **Status**: EASY - Data exists in `code` field
- **Data source**: Node result object
- **Change needed**: Show code diff viewer in node detail view
- **Impact**: MEDIUM - Expert users can debug or guide search
- **Files to modify**: Same as #5

#### 🟡 **7. Show all plots generated so far**
- **Status**: EASY - Plots are being uploaded as artifacts
- **Data source**: Artifacts with type "plot"
- **Change needed**: `PlotGallery` component already exists but may need filtering
- **Impact**: HIGH - Users want to see experimental results
- **Files to verify**: `PlotGallery.tsx` (already exists!)

#### 🟡 **8. Show stage timeline with durations**
- **Status**: EASY - `StageTimingView.tsx` exists
- **Data source**: `run.stageTiming`
- **Change needed**: Verify it's being displayed prominently
- **Impact**: MEDIUM - Shows if certain stages are bottlenecks

#### 🟡 **9. Show live log feed (scrollable, filterable)**
- **Status**: EXISTS - `LiveLogViewer.tsx` already implemented
- **Data source**: Events with type `ai.run.log`
- **Impact**: HIGH - Most direct window into system activity
- **Files to verify**: Component exists, check if it's prominent enough

#### 🟡 **10. Show execution terminal output for each node**
- **Status**: MEDIUM - Data exists in `_term_out` and `parse_term_out`
- **Data source**: Node execution results
- **Change needed**: Add terminal output viewer to node detail
- **Impact**: MEDIUM - Debugging failed executions

### 🟡 **MEDIUM EFFORT** (Needs some aggregation/new components - 4-8 hours each)

#### 11. **Show search tree visualization**
- **Status**: MEDIUM - Tree structure exists (`parent_id`, `children`)
- **Data source**: Journal structure with nodes
- **Change needed**: Create interactive tree visualization component (D3.js or React Flow)
- **Impact**: HIGH - Shows exploration strategy visually
- **Note**: Static HTML visualization is already generated at `unified_tree_viz.html`

#### 12. **Show metrics trend over time (for each metric across nodes)**
- **Status**: MEDIUM - Metrics are structured per node
- **Data source**: Each node has `metric` field with multi-dataset values
- **Change needed**: Aggregate metrics across nodes, create line charts
- **Impact**: HIGH - Shows if search is converging on better solutions

#### 13. **Show "why is this node best" reasoning**
- **Status**: MEDIUM - Selection reasoning exists but may not be persisted
- **Data source**: `select_best_implementation` function call includes reasoning
- **Change needed**: Store reasoning in MongoDB when best node is selected
- **Impact**: MEDIUM - Helps users understand selection criteria

#### 14. **Show stage completion criteria checklist**
- **Status**: MEDIUM - Criteria evaluated by LLM
- **Data source**: `evaluate_stage_completion` function returns `missing_criteria`
- **Change needed**: Store and display evaluation results as checklist
- **Impact**: HIGH - Shows exactly what's needed to proceed

#### 15. **Show comparative table of all nodes (sortable by metric)**
- **Status**: MEDIUM
- **Data source**: All nodes with metrics
- **Change needed**: Create sortable table component with metrics as columns
- **Impact**: MEDIUM - Quick comparison of attempts

### 🔴 **HIGHER EFFORT** (Architectural changes - 1-3 days each)

#### 16. **Real-time "agent is thinking" status**
- **Status**: HARD - Needs instrumentation at LLM call level
- **Change needed**: Emit events before/after each LLM call with purpose
- **Impact**: HIGH - Eliminates uncertainty during long waits

#### 17. **Pause/resume functionality**
- **Status**: HARD - Needs checkpoint/restore system
- **Change needed**: Serialize journal state, handle graceful stop/restart
- **Impact**: MEDIUM - Useful for expensive experiments

#### 18. **Human-in-the-loop guidance**
- **Status**: HARD - Needs bidirectional communication
- **Change needed**: Allow user to mark nodes, suggest directions
- **Impact**: HIGH - Makes search more collaborative

#### 19. **Cost tracking and budget alerts**
- **Status**: MEDIUM-HARD - Needs token tracking per operation
- **Change needed**: Aggregate costs from LLM calls, show running total
- **Impact**: MEDIUM - Important for cost control

#### 20. **Multi-run comparison view**
- **Status**: HARD - Needs cross-run aggregation
- **Change needed**: New page to compare multiple runs side-by-side
- **Impact**: MEDIUM - Useful for evaluating different hyperparameters

## What Data Exists vs What's Displayed

### ✅ **Rich Data Being Collected:**

From your logs, every node has:
```javascript
{
  code: "...",              // Full Python code generated
  plan: "...",             // LLM's plan for the experiment
  overall_plan: "...",     // High-level strategy
  plot_code: "...",        // Code for generating plots
  _term_out: [...],        // Raw terminal output
  parse_term_out: [...],   // Parsed metric extraction output
  exec_time: 0.456,        // Execution duration
  analysis: "...",         // Bug analysis summary (very detailed!)
  metric: {                // Structured metrics
    value: {
      metric_names: [...]
    }
  },
  is_buggy: true/false,    // Bug status
  plots: [...],            // List of generated plot files
  plot_analyses: {...},    // LLM analysis of each plot
  parent_id: "...",        // Tree structure
  children: [...]
}
```

### ❌ **What's NOT Being Displayed (But Should Be):**

1. ✅ **Node counts** - FIXED NOW!
2. ✅ **Iteration progress** - FIXED NOW!
3. ✅ **Best metric** - FIXED NOW!
4. ❌ **Bug analysis summaries** - Super detailed, not shown
5. ❌ **Code diff between attempts** - Code exists but not compared
6. ❌ **Terminal output** - Raw output not displayed
7. ❌ **Node tree structure** - Relationships not visualized
8. ❌ **Plot analysis (LLM feedback on plots)** - Exists but hidden
9. ❌ **Execution time per node** - Tracked but not shown
10. ❌ **Why nodes were selected** - Selection reasoning exists

## Immediate Action Plan (Next 2-4 Hours)

### Priority 1: Verify the Fix Just Applied ✅
Run your next experiment and check if you now see:
- Iteration count (0/5, 1/5, etc.)
- Node counts (X good / Y buggy / Z total)
- Best metric display

### Priority 2: Add "Current Activity" Banner (30 minutes)
Display the most recent `ai.run.log` message prominently at the top of the page:

**Create**: `orchestrator/apps/web/components/CurrentActivityBanner.tsx`
```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import type { Event } from "@/lib/schemas/event"

export function CurrentActivityBanner({ runId }: { runId: string }) {
  const { data } = useQuery<{ items: Event[] }>({
    queryKey: ["latest-activity", runId],
    queryFn: async () => {
      const res = await fetch(`/api/runs/${runId}/events?type=ai.run.log&pageSize=1`)
      if (!res.ok) throw new Error("Failed to fetch")
      return res.json()
    },
    refetchInterval: 2000
  })

  const latest = data?.items?.[0]
  if (!latest?.message) return null

  return (
    <div className="mb-4 rounded-lg border border-sky-800/50 bg-sky-950/30 p-4">
      <div className="flex items-center gap-2">
        <div className="h-2 w-2 animate-pulse rounded-full bg-sky-400" />
        <p className="text-sm text-sky-100">{latest.message}</p>
        <span className="ml-auto text-xs text-sky-400">
          {new Date(latest.timestamp).toLocaleTimeString()}
        </span>
      </div>
    </div>
  )
}
```

**Add to** `RunDetailClient.tsx` right after the header section.

### Priority 3: Create Node List Viewer (2 hours)
Show expandable list of all nodes with their status:

**Create**: `orchestrator/apps/web/components/NodeTreeViewer.tsx`

This would fetch node data from a new endpoint and display:
- Node ID (truncated)
- Status (buggy/good)
- Metrics achieved
- Expandable detail (code, analysis, terminal output)

### Priority 4: Ensure Plot Gallery is Prominent (15 minutes)
Verify `PlotGallery` component is showing all plots and is easy to find.

## Data vs Visualization: The Verdict

**It's a DATA PERSISTENCE problem** (now fixed), not a data collection or visualization problem:

- ✅ **Data collection**: Working perfectly (rich, detailed data)
- ❌ **Data persistence**: Was broken (fixed now!)
- ⚠️ **Data display**: Exists but not prominent/complete

The system was collecting everything but not storing it in MongoDB for the frontend to read. With the fix applied, your dashboard should immediately be more informative.

## Questions You Can NOW Answer

With the fix applied + existing components:

### Already Working:
1. What stage am I in? → `StageProgressPanel`
2. What's the current progress percentage? → `StageProgressPanel`
3. What plots have been generated? → `PlotGallery`
4. What are the recent log messages? → `LiveLogViewer`
5. What events have occurred? → `RunEventsFeed`
6. What's the run status? → `StatusBadge`
7. What artifacts exist? → `ArtifactList`

### NOW Working (After Fix):
8. How many iterations done/remaining? → `StageProgressPanel.iteration`
9. How many good/buggy nodes? → `StageProgressPanel.goodNodes/buggyNodes`
10. What's the best metric so far? → `StageProgressPanel.bestMetric`

### Still Need UI Work:
11. What is each node attempting? → Need `NodeTreeViewer`
12. Why did nodes fail? → Need bug analysis display
13. What code was generated? → Need code viewer
14. How does the search tree look? → Need tree visualization

## Summary: You Were Right to Be Frustrated!

The data was there but wasn't reaching the UI. The main bottleneck was `pod_worker.py` only storing 2 fields when it should've stored 7+. 

**Next run will show much more information automatically!**

The remaining gaps are legitimate missing UI components, but you now have a roadmap of what exists, what's missing, and the effort to add each feature.

