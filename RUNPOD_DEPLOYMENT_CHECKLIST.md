# RunPod Deployment Checklist ✅

## 🚨 CRITICAL: Config Schema Update

**You MUST update the config schema or the system will break!**

---

## 📦 Files to Upload to RunPod (in order)

### **1. Config Schema (MUST BE FIRST!)**

```bash
ai_scientist/treesearch/utils/config.py
```

**Why first?** This defines the structure of `bfts_config.yaml`. If you upload the yaml before updating the schema, the system will crash with validation errors.

**What changed:**
- Added `WriteupConfig` dataclass
- Added `writeup: Optional[WriteupConfig]` to main Config

---

### **2. Config YAML**

```bash
bfts_config.yaml
```

**What changed:**
- Added `writeup` section with `big_model`, `small_model`, `plot_model`

---

### **3. Core Backend Files**

```bash
ai_scientist/perform_icbinb_writeup.py    # Bug fixes
pod_worker.py                              # Loads models from config
upload_artifact_helper.py                 # NEW - Auto artifact upload
```

---

### **4. Helper Scripts (Optional)**

```bash
fix_missing_ideajson.py                   # Database fix
manual_writeup.py                         # Manual retry script
```

---

## 🚀 Deployment Steps

### **Step 1: Update Config Schema FIRST**

```bash
# SSH into RunPod
cd /workspace/AI-Scientist-v2\ copy

# Update config.py
nano ai_scientist/treesearch/utils/config.py
# Paste the updated content

# OR use scp
scp ai_scientist/treesearch/utils/config.py root@<POD_IP>:/workspace/AI-Scientist-v2\ copy/ai_scientist/treesearch/utils/
```

### **Step 2: Update bfts_config.yaml**

```bash
nano bfts_config.yaml
# Add the writeup section
```

### **Step 3: Verify Config Loads**

```bash
source .venv/bin/activate  # or your venv path

python -c "
from ai_scientist.treesearch.utils.config import load_cfg
from pathlib import Path
cfg = load_cfg(Path('bfts_config.yaml'))
print('✓ Config loaded successfully!')
print('✓ Writeup config:', cfg.writeup)
"
```

**Expected output:**
```
✓ Config loaded successfully!
✓ Writeup config: WriteupConfig(big_model='gpt-5', small_model='gpt-5-mini', plot_model='gpt-5-mini')
```

### **Step 4: Upload Remaining Files**

```bash
# Update perform_icbinb_writeup.py
nano ai_scientist/perform_icbinb_writeup.py

# Update pod_worker.py
nano pod_worker.py

# Add new helper script
nano upload_artifact_helper.py
chmod +x upload_artifact_helper.py

# Optional helpers
nano fix_missing_ideajson.py
nano manual_writeup.py
chmod +x manual_writeup.py
```

### **Step 5: Restart Worker**

```bash
# Kill existing worker
pkill -f pod_worker.py

# Restart with new code
source .venv/bin/activate
python pod_worker.py
```

---

## 🧪 Testing

### **Test 1: Config Validation**

```bash
python -c "
import yaml
from ai_scientist.treesearch.utils.config import load_cfg
from pathlib import Path

# Test yaml loads
with open('bfts_config.yaml') as f:
    raw = yaml.safe_load(f)
    print('✓ YAML parses:', raw.get('writeup'))

# Test config class loads
cfg = load_cfg(Path('bfts_config.yaml'))
print('✓ Config validates:', cfg.writeup)
"
```

### **Test 2: Pod Worker Loads Config**

```bash
python -c "
import os
import yaml

# Simulate pod_worker.py config loading
config_path = 'bfts_config.yaml'
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

plot_model = config.get('writeup', {}).get('plot_model', 'gpt-5-mini')
small_model = config.get('writeup', {}).get('small_model', 'gpt-5-mini')
big_model = config.get('writeup', {}).get('big_model', 'gpt-5')

print(f'✓ pod_worker.py will use:')
print(f'  plot_model:  {plot_model}')
print(f'  small_model: {small_model}')
print(f'  big_model:   {big_model}')
"
```

### **Test 3: Run Database Fix**

```bash
# Fix any existing hypotheses missing ideaJson
python fix_missing_ideajson.py
```

---

## 📋 Complete File List

| Order | File | Location | Purpose |
|-------|------|----------|---------|
| 1️⃣ | `config.py` | `ai_scientist/treesearch/utils/` | ⚠️ **Config schema** |
| 2️⃣ | `bfts_config.yaml` | Root | Model configuration |
| 3️⃣ | `perform_icbinb_writeup.py` | `ai_scientist/` | Bug fixes |
| 4️⃣ | `pod_worker.py` | Root | Config loading |
| 5️⃣ | `upload_artifact_helper.py` | Root | Artifact upload |
| 6️⃣ | `fix_missing_ideajson.py` | Root | Database fix (run once) |
| 7️⃣ | `manual_writeup.py` | Root | Manual retry (optional) |

---

## ⚠️ Common Mistakes

### ❌ **Mistake 1: Upload yaml before config.py**
**Error:** `OmegaConf validation error: unexpected key 'writeup'`

**Fix:** Always upload `config.py` first!

### ❌ **Mistake 2: Forget to restart worker**
**Error:** Old code still running, changes not applied

**Fix:** Always `pkill -f pod_worker.py` and restart

### ❌ **Mistake 3: Wrong Python environment**
**Error:** `ModuleNotFoundError: No module named 'omegaconf'`

**Fix:** Activate venv: `source .venv/bin/activate`

### ❌ **Mistake 4: Don't make helper executable**
**Error:** `Permission denied: upload_artifact_helper.py`

**Fix:** `chmod +x upload_artifact_helper.py`

---

## 🎯 Quick Deploy Script

```bash
#!/bin/bash
# deploy_to_runpod.sh

POD_IP="your-pod-ip"
POD_PATH="/workspace/AI-Scientist-v2 copy"

echo "🚀 Deploying to RunPod..."

# 1. Config schema FIRST
echo "1️⃣ Uploading config schema..."
scp ai_scientist/treesearch/utils/config.py root@$POD_IP:$POD_PATH/ai_scientist/treesearch/utils/

# 2. Config yaml
echo "2️⃣ Uploading bfts_config.yaml..."
scp bfts_config.yaml root@$POD_IP:$POD_PATH/

# 3. Core files
echo "3️⃣ Uploading core files..."
scp ai_scientist/perform_icbinb_writeup.py root@$POD_IP:$POD_PATH/ai_scientist/
scp pod_worker.py root@$POD_IP:$POD_PATH/
scp upload_artifact_helper.py root@$POD_IP:$POD_PATH/

# 4. Optional helpers
echo "4️⃣ Uploading helpers..."
scp fix_missing_ideajson.py root@$POD_IP:$POD_PATH/
scp manual_writeup.py root@$POD_IP:$POD_PATH/

# 5. Set permissions
echo "5️⃣ Setting permissions..."
ssh root@$POD_IP "cd $POD_PATH && chmod +x upload_artifact_helper.py manual_writeup.py"

# 6. Restart worker
echo "6️⃣ Restarting worker..."
ssh root@$POD_IP "pkill -f pod_worker.py; cd $POD_PATH && source .venv/bin/activate && nohup python pod_worker.py > worker.log 2>&1 &"

echo "✅ Deployment complete!"
```

---

## 🔍 Verification Commands

After deployment, run these on the pod to verify:

```bash
# Check config schema has writeup
python -c "from ai_scientist.treesearch.utils.config import WriteupConfig; print(WriteupConfig.__annotations__)"

# Check yaml has writeup section
grep -A3 "^writeup:" bfts_config.yaml

# Check worker is running
ps aux | grep pod_worker.py

# Check worker log
tail -f worker.log
```

---

## 📞 Troubleshooting

### **Issue: "unexpected key 'writeup'"**
**Solution:** You uploaded yaml before config.py. Upload config.py first, then restart worker.

### **Issue: "AttributeError: 'Config' object has no attribute 'writeup'"**
**Solution:** Old config.py in memory. Restart worker.

### **Issue: Worker keeps using old models**
**Solution:** Check yaml actually has writeup section. Verify with: `grep writeup bfts_config.yaml`

---

## ✅ Success Checklist

- [ ] `config.py` updated and uploaded FIRST
- [ ] `bfts_config.yaml` has writeup section
- [ ] Config validation test passes
- [ ] `perform_icbinb_writeup.py` updated
- [ ] `pod_worker.py` updated  
- [ ] `upload_artifact_helper.py` added and executable
- [ ] Worker restarted successfully
- [ ] Worker log shows no config errors
- [ ] Test run uses gpt-5/gpt-5-mini (check logs)

---

**TL;DR:**
1. Upload `config.py` FIRST ⚠️
2. Then upload `bfts_config.yaml`
3. Verify config loads
4. Upload other files
5. Restart worker
6. Test!

