# Paper Writeup Bug Fixes & Feature Additions

## 🐛 Bugs Fixed

### 1. **Critical String Formatting Bug in Writeup Reflection** ✅
**File:** `ai_scientist/perform_icbinb_writeup.py:1211`

**Issue:** Missing f-string prefix caused reflection prompt to send literal `{reflection_page_info}` to the LLM instead of actual page info.

```python
# BEFORE (❌ Bug)
final_reflection_prompt = """{reflection_page_info}
USE MINIMAL EDITS TO OPTIMIZE THE PAGE LIMIT USAGE."""

# AFTER (✅ Fixed)
final_reflection_prompt = f"""{reflection_page_info}
USE MINIMAL EDITS TO OPTIMIZE THE PAGE LIMIT USAGE."""
```

**Impact:** This caused the final reflection to fail silently, resulting in "Writeup process did not complete successfully."

### 2. **Silent Failure - No Error Logging** ✅
**File:** `ai_scientist/perform_icbinb_writeup.py:1253-1262`

**Issue:** When PDF generation failed, the function returned `False` without explaining why.

**Added:**
- Detailed error logging for missing LaTeX code blocks
- PDF existence check with helpful error message
- Response preview for debugging

### 3. **Seed Data Missing ideaJson** ✅
**File:** `orchestrator/apps/web/scripts/seed.ts`

**Issue:** Seed hypotheses were created without `ideaJson`, causing all seed-based runs to fail with "Hypothesis missing ideaJson."

**Fixed:** Added proper `ideaJson` structure to all three seed hypotheses.

---

## ✨ New Features

### **"Retry Paper Generation" Button** 🎯

Added ability to manually retry paper generation for failed runs directly from the frontend.

#### **Backend API Endpoint**
**New File:** `orchestrator/apps/web/app/api/runs/[id]/retry-writeup/route.ts`

- POST endpoint: `/api/runs/[id]/retry-writeup`
- Finds experiment directory by run ID
- Spawns detached Python process to run `perform_icbinb_writeup`
- Uses gpt-5 and gpt-5-mini from config
- Updates run status to track retry

#### **Frontend Button**
**Modified:** `orchestrator/apps/web/components/RunActions.tsx`

- New "Retry Paper Generation" button (blue styling)
- Only shows when run status = "FAILED"
- Confirms before retrying
- Shows success message after starting
- Auto-refreshes page after 2 seconds

**Modified:** `orchestrator/apps/web/components/RunDetailClient.tsx`

- Added `canRetryWriteup` logic
- Passes `status` and `canRetryWriteup` props to RunActions

#### **Usage:**
1. Navigate to a FAILED run's detail page
2. Click "Retry Paper Generation" button
3. Confirm the action
4. Wait a few minutes for the writeup to complete
5. Refresh to see the new PDF in Artifacts

---

## 🔧 Supporting Scripts

### **Manual Writeup Script**
**File:** `manual_writeup.py`

Standalone script to manually run writeup for any experiment:

```bash
python manual_writeup.py experiments/2025-10-23_12-57-41_crystal_llms_run_349fca1e-1e8c-4992-8fc3-f38c644c0aee
```

Features:
- Loads models from `bfts_config.yaml`
- Copies experiment results
- Aggregates plots
- Gathers citations
- Generates paper
- Cleans up temp files

### **Fix Missing ideaJson Script**
**File:** `fix_missing_ideajson.py`

Repairs existing database entries missing `ideaJson`:

```bash
python fix_missing_ideajson.py
```

Automatically adds proper ideaJson structure to all hypotheses that are missing it.

---

## 📝 How To Use

### **From Frontend:**
1. Go to Runs page
2. Click on a FAILED run
3. Click "Retry Paper Generation" button
4. Wait 5-10 minutes
5. Check Artifacts section for PDF

### **From Command Line (Pod):**
```bash
cd /workspace/AI-Scientist-v2\ copy
source .venv/bin/activate

python -m ai_scientist.perform_icbinb_writeup \
  --folder experiments/[your-experiment-folder] \
  --model gpt-5-mini \
  --big-model gpt-5 \
  --num-cite-rounds 15 \
  --page-limit 4
```

### **From Local Machine:**
```bash
cd /Users/jessica/AEStudio/agi/AI-Scientist-v2
source .venv/bin/activate

python manual_writeup.py experiments/[your-experiment-folder]
```

---

## 🎯 What Was Fixed

| Issue | Status | Location |
|-------|--------|----------|
| String formatting bug in reflection | ✅ Fixed | `perform_icbinb_writeup.py:1211` |
| Silent failure - no error logs | ✅ Fixed | `perform_icbinb_writeup.py:1253-1262` |
| Seed data missing ideaJson | ✅ Fixed | `seed.ts:17-66` |
| No way to retry writeup from frontend | ✅ Added | New API + UI button |
| Unclear error messages | ✅ Improved | Added detailed logging |

---

## 🚀 Next Steps

1. **Fix existing hypotheses:** Run `python fix_missing_ideajson.py`
2. **Retry failed runs:** Use the new "Retry Paper Generation" button
3. **Monitor logs:** Check for better error messages in future runs

---

## 📚 Where Papers Appear in Frontend

Papers show up in **two places** on the run detail page:

1. **Artifacts Section** (right side)
   - Shows PDF with download button
   - Located below the live logs viewer
   
2. **Plots Section** (if available)
   - Shows generated plot images
   - Updates in real-time during experiments

---

## ⚠️ Important Notes

1. **No Duplicate Folders:** The experiment folder is NOT duplicated - it uses the same timestamped folder created during the initial run.

2. **Model Configuration:** The system now correctly uses `gpt-5` and `gpt-5-mini` from `bfts_config.yaml` instead of hardcoded models.

3. **Async Process:** The retry button spawns a detached process, so the frontend won't block while the paper is being generated.

4. **Check Back:** After clicking retry, wait 5-10 minutes then refresh the page to see the PDF.

