# Live Writeup Retry - Real-Time Updates ✨

## Problem Solved

**Before:**
- ❌ "Wait 5-10 minutes and refresh"
- ❌ No live feedback
- ❌ No automatic artifact upload

**After:**
- ✅ **Real-time event streaming** to frontend
- ✅ **Live logs** appear instantly in the UI
- ✅ **Automatic artifact upload** when PDF is ready
- ✅ **No refresh needed** - everything updates live!

---

## How It Works

### 1. **Event-Driven Architecture**

When you click "Retry Paper Generation":

```
Click Button
    ↓
API creates wrapper script
    ↓
Wrapper spawns Python process
    ↓
Every output line → MongoDB event
    ↓
Frontend polls events (every 5s)
    ↓
Live logs update in UI ✨
```

### 2. **Event Types Emitted**

| Event Type | When | Shows In UI |
|------------|------|-------------|
| `ai.run.paper.retry.started` | Button clicked | "Paper generation retry started" |
| `ai.run.log` | Every stdout line | Live log viewer |
| `ai.run.paper.generated` | PDF created | Success message |
| `ai.run.artifact.registered` | PDF uploaded | Artifacts list updates |
| `ai.run.paper.failed` | No PDF found | Error message |

### 3. **Automatic Artifact Upload**

New helper script: `upload_artifact_helper.py`

```python
# Automatically called when PDF is generated:
1. Gets presigned S3 URL
2. Uploads PDF file
3. Calculates SHA256 hash
4. Registers artifact in database
5. Emits event → UI updates
```

---

## User Experience

### **Step-by-Step:**

1. **Navigate** to a FAILED run
2. **Click** blue "Retry Paper Generation" button
3. **Confirm** the dialog
4. **Watch** live logs appear instantly:
   ```
   📊 Aggregating plots...
   Using OpenAI API with model gpt-5-mini.
   📄 Gathering citations...
   ✍️  Writing paper with gpt-5...
   [DEBUG] Calling gpt-5 with 2 messages
   ...
   Output written on template.pdf (5 pages, 185759 bytes).
   ✅ Paper PDF generated successfully
   📤 Uploading paper artifact...
   ✅ Paper artifact uploaded
   ✨ Writeup retry complete!
   ```
5. **See** PDF appear in Artifacts section automatically
6. **Download** the paper immediately

### **No Manual Steps Required!**

---

## Technical Details

### **Files Modified:**

1. **`orchestrator/apps/web/app/api/runs/[id]/retry-writeup/route.ts`**
   - Creates bash wrapper script with event emission
   - Uses MOST RECENT experiment directory (no duplicates)
   - Emits events at every step
   - Calls upload helper automatically

2. **`orchestrator/apps/web/components/RunActions.tsx`**
   - Updated confirmation message
   - Shows success with checkmark
   - Displays response message from API

3. **`upload_artifact_helper.py`** (NEW)
   - Handles S3 presigned upload
   - Registers artifact in database
   - Emits artifact.registered event

### **Environment Variables Used:**

```bash
EXPERIMENT_ROOT="/workspace/AI-Scientist-v2 copy/experiments"
AI_SCIENTIST_ROOT="/workspace/AI-Scientist-v2 copy"
PYTHON_PATH="python"
MONGODB_URL="mongodb://..."
CONTROL_PLANE_URL="https://..."
```

---

## Experiment Directory Handling

### **Problem:** Multiple folders with same run ID

**Solution:** Always use the **MOST RECENT** directory:

```typescript
const experimentDirs = fs.readdirSync(experimentRoot)
  .filter(dir => dir.includes(id))
  .sort()  // Timestamp order

// Use LAST (most recent) directory
const experimentDir = experimentDirs[experimentDirs.length - 1]
```

This ensures:
- ✅ No new folders created
- ✅ Always works with the latest attempt
- ✅ Handles retry scenarios correctly

---

## Event Emission Pattern

### **Bash Function:**

```bash
emit_event() {
  local event_type=$1
  local message=$2
  python3 << PYEOF
import os
from pymongo import MongoClient
from datetime import datetime
from uuid import uuid4

client = MongoClient(os.environ.get('MONGODB_URL'))
db = client['ai-scientist']
db.events.insert_one({
    'id': str(uuid4()),
    'specversion': '1.0',
    'source': 'writeup-retry',
    'type': '$event_type',
    'subject': 'run/$RUN_ID',
    'time': datetime.utcnow().isoformat() + 'Z',
    'datacontenttype': 'application/json',
    'data': {'message': '$message'}
})
PYEOF
}
```

### **Usage in Script:**

```bash
# Stream all output to events
python -m ai_scientist.perform_icbinb_writeup \
  --folder "${experimentDir}" \
  ... 2>&1 | while read line; do
  echo "$line"
  emit_event "ai.run.log" "$line"
done
```

---

## Frontend Integration

The existing `RunDetailClient` component already:
- ✅ Polls for events every 5 seconds
- ✅ Updates live logs automatically
- ✅ Refreshes artifacts list
- ✅ Shows real-time progress

**No additional frontend changes needed!**

---

## Testing

### **Test the Flow:**

1. Create a run that fails during writeup
2. Click "Retry Paper Generation"
3. Observe:
   - Confirmation dialog mentions live logs
   - Success message appears
   - Live logs start showing immediately
   - PDF appears in artifacts when ready
   - All happens without manual refresh!

---

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Feedback** | None | Live streaming |
| **Wait time** | Unknown | Watch progress |
| **Manual steps** | Refresh + check | Zero |
| **Artifact upload** | Manual | Automatic |
| **User confidence** | Low (black box) | High (transparent) |
| **Debugging** | Check pod logs | See errors in UI |

---

## Future Enhancements

Potential improvements:
- [ ] Progress bar with stages (citations → writing → reflection)
- [ ] Estimated time remaining
- [ ] Cancel retry button
- [ ] Retry with different models
- [ ] Batch retry for multiple failed runs

---

## Summary

**The system is now fully event-driven and provides real-time feedback!**

✨ Click button → Watch live logs → PDF appears automatically → No refresh needed! ✨

---

*This update transforms the retry experience from "fire and forget" to "watch and celebrate"!* 🎉

