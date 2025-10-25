# Quick Dashboard Reference

## 🎯 What Just Got Fixed

### Problem
Dashboard showed basically nothing during Stage 1:
```
Stage 1: Initial Implementation
Progress: 0%

[crickets... is it frozen? what's happening?]
```

### Solution
Now shows EVERYTHING:
```
🔵 📤 Submitting 3 node(s): 2 debugging, 1 improving     10:28:45 AM

┌─────────────────────────────────────────────────────────┐
│ Stage 1: Initial Implementation               34% │
│ ▓▓▓▓▓▓▓░░░░░░░░░░░░░                                  │
│                                                         │
│ Iteration:  2/5                 Elapsed:  6m 35s       │
│ Nodes:      0 good / 3 buggy    ETA:      ~13m 12s     │
│ Total:      3 nodes                                     │
│                                                         │
│ Best Metric:                                            │
│ validation R↑ closed_loop: 0.3418                      │
└─────────────────────────────────────────────────────────┘
```

## 📊 What Data You Can Now See

| Info | Where | Updates |
|------|-------|---------|
| **Current activity** | Blue banner at top | Every 2s |
| **Iteration progress** | Stage panel | Every iteration |
| **Node counts (good/buggy)** | Stage panel | Real-time |
| **Best metric** | Stage panel | When improved |
| **ETA** | Stage panel | Calculated live |
| **Live logs** | Live Logs panel | Every 2s |
| **Plots** | Plot Gallery | As generated |
| **All events** | All Events section | Every 5s |

## 🚦 Activity Banner Color Codes

| Color | Meaning | Example |
|-------|---------|---------|
| 🟢 Green | Success/Completion | "✅ Stage completed!" |
| 🔵 Blue | Normal Activity | "📤 Submitting 3 nodes..." |
| 🟡 Amber | Warning | "⚠️ No plots found" |
| 🔴 Red | Error | "❌ Execution failed" |

## 🔍 Understanding Node Counts

**Good nodes** = Implementations that ran without bugs
**Buggy nodes** = Implementations that failed execution or produced errors
**Total nodes** = All attempts made so far

### What's Normal?
- Early stage: **0 good / 3-5 buggy** → System is debugging initial attempts
- Mid stage: **1-2 good / 5-10 buggy** → Finding working solutions
- Late stage: **3+ good / 10+ buggy** → Refining best approaches

### When to Worry?
- ❌ **0 good / 15+ buggy** after 30+ minutes → May need intervention
- ✅ **1+ good / any buggy** → Experiment is progressing fine

## 📈 Understanding Progress

**Progress % = (current_iteration / max_iterations) × 100**

**NOT based on having "good" nodes** - the system will iterate the max number of times regardless, continually trying to debug and improve.

### Example Flow:
```
Iteration 1/5 (20%) → Draft 3 new implementations
  ↓
All 3 buggy → Detailed bug analysis generated
  ↓
Iteration 2/5 (40%) → Debug those 3 buggy nodes
  ↓
1 good, 2 still buggy → Select best, debug others
  ↓
Iteration 3/5 (60%) → Improve the 1 good, debug 2 buggy
  ↓
... continues until 5/5 or stage completion criteria met
```

## 🎨 Where Everything Is

```
Run Detail Page Layout:
┌────────────────────────────────────────────┐
│ Header: Run ID, Status Badge               │
│ Actions: Cancel, Retry Writeup             │
├────────────────────────────────────────────┤
│ 🔵 CURRENT ACTIVITY BANNER ← NEW!          │
├────────────────────────────────────────────┤
│ ┌────────────────┐  ┌──────────────────┐   │
│ │ Stage Progress │  │ Stage Timing     │   │
│ │  - Iteration   │  │  - Per stage     │   │
│ │  - Nodes       │  │  - Durations     │   │
│ │  - Best Metric │  │                  │   │
│ └────────────────┘  └──────────────────┘   │
├────────────────────────────────────────────┤
│ Pipeline Stages Overview                   │
│  - Stage 1, 2, 3, 4 progress bars          │
├────────────────────────────────────────────┤
│ 📊 Plot Gallery                            │
│  - All generated plots                     │
├────────────────────────────────────────────┤
│ ┌──────────────┐  ┌────────────────────┐   │
│ │ Live Logs    │  │ Artifacts          │   │
│ │ (scrollable) │  │  - PDFs, plots     │   │
│ └──────────────┘  └────────────────────┘   │
├────────────────────────────────────────────┤
│ All Events (detailed feed)                 │
└────────────────────────────────────────────┘
```

## 🛠️ What Changed (Technical)

### Backend (`pod_worker.py`)
```python
# BEFORE: Only 2 fields
"currentStage": {
    "name": display_name,
    "progress": progress
}

# AFTER: 7 fields (5 new!)
"currentStage": {
    "name": display_name,
    "progress": progress,
    "iteration": iteration,              # NEW
    "maxIterations": max_iterations,      # NEW
    "goodNodes": good_nodes,              # NEW
    "buggyNodes": buggy_nodes,            # NEW
    "totalNodes": total_nodes,            # NEW
    "bestMetric": data.get("best_metric") # NEW
}
```

### Frontend
- ✅ Added `CurrentActivityBanner.tsx` component
- ✅ Integrated into `RunDetailClient.tsx`
- ✅ `StageProgressPanel.tsx` now receives data it needs

## 💡 Pro Tips

### To See Maximum Detail:
1. Open **Live Logs** panel (filters: all/info/warn/error)
2. Expand **All Events** section
3. Keep **Plot Gallery** visible

### To Focus on Progress:
1. Watch **Activity Banner** (top)
2. Monitor **Stage Progress Panel** (iteration count)
3. Check **Best Metric** (is quality improving?)

### If It Seems Stuck:
1. Check **Activity Banner** - is message changing?
2. Check **Elapsed Time** - is it increasing?
3. Check **Live Logs** - new entries appearing?
4. If all three YES → system is working, just slow
5. If all three NO → might be frozen, check pod status

## 🐛 Troubleshooting

### "I don't see the activity banner"
- Is the run status "RUNNING"? (banner only shows for active runs)
- Check browser console for errors
- Try hard refresh (Cmd+Shift+R)

### "Node counts showing 0/0/0"
- This happens briefly at startup before first iteration
- Should update within 30-60 seconds
- If persists >2 minutes, check if run is actually running

### "Best metric shows 'null'"
- Normal if no valid metrics extracted yet
- Wait for first node with valid output
- Some experiments may not have extractable metrics early on

### "Activity banner stuck on old message"
- Events may be delayed - check "All Events" for recent activity
- Try refreshing the page
- Check pod worker is still sending heartbeats

## 📚 Related Docs

- **Full improvement roadmap**: `DASHBOARD_IMPROVEMENTS.md`
- **Technical fix details**: `DASHBOARD_FIX_SUMMARY.md`
- **Stage definitions**: Look for `STAGE_DESCRIPTIONS` in code

## ⚡ Quick Answers

**Q: How long should Stage 1 take?**  
A: Typically 10-30 minutes for 3-5 iterations

**Q: Is it normal to have all buggy nodes initially?**  
A: Yes! System debugs iteratively

**Q: When will I see "good nodes"?**  
A: Usually by iteration 2-3, sometimes iteration 1

**Q: What's a "good" best metric value?**  
A: Depends on your experiment - just watch if it's improving

**Q: Can I intervene during a run?**  
A: Currently limited to canceling - human-in-loop planned

**Q: Where are detailed bug reports?**  
A: Coming soon! Data exists, need UI component (see DASHBOARD_IMPROVEMENTS.md)

---

🎉 **You now have full visibility into your experiments!**

No more wondering "is it frozen or just slow?" - you'll know exactly what's happening at every moment.

