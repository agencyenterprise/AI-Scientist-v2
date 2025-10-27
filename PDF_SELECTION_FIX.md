# PDF Selection Fix for Auto-Validation

## Problem
The auto-validation (Stage 4) was naively picking `pdf_files[0]` - the first PDF returned by `os.listdir()`, which has **no guaranteed order**. This meant it could review:
- A draft PDF instead of the final one
- `reflection1.pdf` instead of `reflection3.pdf`  
- A random PDF when multiple exist

## Solution
Ported Sakana's `find_pdf_path_for_review()` logic into `find_best_pdf_for_review()` function.

## Smart Selection Priority

The function now selects PDFs in this priority order:

1. **"final" reflection PDFs** (highest priority)
   - `reflection_final.pdf`
   - `experiment_reflection_final_page_limit.pdf`

2. **Highest numbered reflection**
   - `reflection3.pdf` > `reflection2.pdf` > `reflection1.pdf`
   - Uses regex: `r"reflection[_.]?(\d+)"`

3. **Any reflection PDF**
   - `reflection.pdf`

4. **Non-draft PDFs**
   - Avoids PDFs with "draft" in the name

5. **Any PDF** (fallback)
   - If nothing else matches

## Changes Made

### 1. Added `re` import
```python
import re
```

### 2. Added selection function (lines 27-70)
```python
def find_best_pdf_for_review(pdf_files):
    """
    Intelligently select the best PDF for review from a list of PDFs.
    Prioritizes: final PDFs > highest numbered reflections > any reflection > any PDF
    """
    # ... smart selection logic ...
```

### 3. Updated Stage 4 to use smart selection (lines 958-962)
```python
if pdf_files:
    # Smart PDF selection: prefer final > highest numbered > any reflection
    pdf_to_review = find_best_pdf_for_review(pdf_files)
    pdf_path = os.path.join(idea_dir, pdf_to_review)
    event_emitter.log(run_id, f"Loading paper from: {pdf_to_review}", "info", "Stage_4")
    print(f"📄 Selected PDF for review: {pdf_to_review}")
```

## Example Behavior

### Scenario 1: Multiple reflection PDFs
```
PDFs in directory:
- experiment_reflection1.pdf
- experiment_reflection2.pdf
- experiment_reflection_final.pdf  ✓ SELECTED (has "final")
- experiment.pdf
```

### Scenario 2: Numbered reflections
```
PDFs in directory:
- experiment_reflection_1.pdf
- experiment_reflection_2.pdf
- experiment_reflection_3.pdf  ✓ SELECTED (highest number)
```

### Scenario 3: No reflections
```
PDFs in directory:
- experiment_draft.pdf
- experiment.pdf  ✓ SELECTED (no "draft")
```

### Scenario 4: Only one PDF
```
PDFs in directory:
- experiment.pdf  ✓ SELECTED (only option)
```

## Logging
The stage now logs which PDF was selected:
```
📄 Selected PDF for review: experiment_reflection_final.pdf
```

This appears in:
- Console output
- Stage 4 logs  
- Live log viewer in UI

## Testing
Syntax check passed:
```bash
python -m py_compile pod_worker.py  ✓
```

## Benefits
✅ Always reviews the most recent/final version
✅ Matches Sakana's original behavior
✅ Deterministic PDF selection
✅ Clear logging of which PDF was chosen

