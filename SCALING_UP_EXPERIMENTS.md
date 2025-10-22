# Scaling Up AI Scientist Experiments for 6x L40 GPUs

## Current State (Underutilized)
- **GPUs**: 6x L40 (48GB VRAM each) = 288GB total
- **Current usage**: <1% (distilgpt2 ~330MB, 16 samples, 2 epochs)
- **Cost**: ~$3.60/hour for 3x L40 per pod
- **Result**: Massive waste of resources

## Option 1: Scale DOWN (Cost Savings)

### Recommended Hardware
- **1x RTX 3060 Ti (12GB)** or **1x RTX 4070 (12GB)**
- Cost: ~$0.20-0.30/hour
- **Savings: ~94%**
- Handles current experiments perfectly

### When to Use This
- Rapid prototyping with small models
- Testing AI Scientist pipeline
- Budget-constrained research

## Option 2: Scale UP (Recommended for L40s) ⭐

### Make Experiments Worthy of Your Hardware

#### 1. Use Larger Models

```python
# Current: distilgpt2 (82M params, ~330MB)
# Upgrade to:

MODELS = [
    "gpt2",              # 124M params (~500MB)
    "gpt2-medium",       # 355M params (~1.4GB)
    "gpt2-large",        # 774M params (~3GB)
    "facebook/opt-1.3b", # 1.3B params (~5GB)
    "facebook/opt-2.7b", # 2.7B params (~10GB)
    "meta-llama/Llama-2-7b-hf",  # 7B params (~14GB)
]
```

#### 2. Scale Up Datasets

```python
# Current: 12-16 samples
# Upgrade to:

DATASET_SIZES = {
    "train": 10000,   # Instead of 12
    "val": 2000,      # Instead of 4
    "test": 2000,     # Instead of 4
}
```

#### 3. Proper Training

```python
# Current: 2 epochs, batch_size=128
# Upgrade to:

TRAINING_CONFIG = {
    "epochs": 20,           # Proper convergence
    "batch_size": 64,       # Larger batches with gradient accumulation
    "learning_rates": [1e-5, 5e-5, 1e-4],  # Grid search
    "warmup_steps": 500,
    "weight_decay": [0.01, 0.1],
}
```

#### 4. Parallel GPU Assignment

With 10 workers and 6 GPUs:

```python
# Worker-to-GPU mapping
GPU_ASSIGNMENT = {
    "worker_0": "cuda:0",  # Pod 1, GPU 0
    "worker_1": "cuda:1",  # Pod 1, GPU 1
    "worker_2": "cuda:2",  # Pod 1, GPU 2
    "worker_3": "cuda:3",  # Pod 2, GPU 0
    "worker_4": "cuda:4",  # Pod 2, GPU 1
    "worker_5": "cuda:5",  # Pod 2, GPU 2
    # Workers 6-9 share GPUs or wait
}
```

#### 5. Multi-Seed Robustness

```yaml
multi_seed_eval:
  num_seeds: 5  # Instead of 3
  seeds: [42, 123, 456, 789, 1011]
```

## Concrete Config Changes

### bfts_config.yaml Updates

```yaml
experiment:
  num_syn_datasets: 3  # More datasets
  
  # Larger scale experiments
  scale:
    model_sizes: ["gpt2-medium", "gpt2-large", "opt-1.3b"]
    dataset_samples: 5000  # Training samples
    epochs: 15
    batch_size: 32  # Per GPU
    
compute:
  gpu:
    type: "L40"
    count: 3
    vram_gb: 48
  total_pods: 2
  notes: "High-performance setup. Design experiments for 7B+ models and large datasets."
  
agent:
  num_workers: 6  # Match GPU count for 1:1 mapping
  stages:
    stage1_max_iters: 15  # More exploration
    stage2_max_iters: 20  # Extensive baseline tuning
    stage3_max_iters: 25  # Deep creative research
    stage4_max_iters: 30  # Comprehensive ablations
```

## Expected Impact

### With Scaled-Up Experiments

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| GPU Utilization | <1% | 60-80% | 60-80x |
| Model Size | 82M | 1.3B - 7B | 16-85x |
| Training Samples | 16 | 10,000 | 625x |
| Epochs | 2 | 20 | 10x |
| Experiment Quality | Low | High | Publishable |
| Cost Efficiency | Terrible | Good | Worth it |

### Timeline Changes

| Phase | Before | After (Scaled) | Why |
|-------|--------|----------------|-----|
| Stage 3 | 1h 46min | 4-6 hours | Larger models, more data |
| Stage 4 | 1h 48min | 5-8 hours | Comprehensive ablations |
| **Total** | **5 hours** | **12-18 hours** | Real research quality |

## Implementation Steps

### 1. Update Config (Done ✓)
```bash
# Already added compute section to bfts_config.yaml
```

### 2. Modify Prompts
Add to system prompts in `ai_scientist/treesearch/journal.py`:

```python
compute_resources = f"""
Available Compute Resources:
- GPUs: {config.compute.gpu.count}x {config.compute.gpu.type} ({config.compute.gpu.vram_gb}GB VRAM each)
- Total Pods: {config.compute.total_pods}
- Total VRAM: {config.compute.gpu.count * config.compute.total_pods * config.compute.gpu.vram_gb}GB

Design experiments that leverage this hardware:
- Use models up to 7B parameters (requires ~14GB VRAM)
- Large batch sizes and datasets
- Extensive hyperparameter sweeps
- Multi-seed evaluations for statistical robustness
"""
```

### 3. Test Scaled Experiment
```bash
# Create a new idea that specifies larger models
python ai_scientist/perform_ideation_temp_free.py \
    --workshop-file "ideas/my_idea.pdf" \
    --model gpt-5 \
    --max-num-generations 5
```

### 4. Monitor GPU Usage
```bash
# On RunPod, watch GPU utilization
watch -n 1 nvidia-smi
```

## Cost Analysis

### Current Setup (Underutilized)
- **Hardware**: 6x L40 (3 per pod)
- **Cost**: ~$1.80/hr per pod × 2 = **$3.60/hour**
- **Per experiment**: ~$18 (5 hours)
- **Utilization**: <1%
- **Value**: ❌ Poor

### Scaled-Up (Recommended)
- **Hardware**: Same (6x L40)
- **Cost**: **$3.60/hour** 
- **Per experiment**: ~$54 (15 hours)
- **Utilization**: 60-80%
- **Value**: ✅ Excellent (publication-quality)

### Scaled-Down (Alternative)
- **Hardware**: 1x RTX 3060
- **Cost**: **$0.25/hour**
- **Per experiment**: ~$1.25 (5 hours)
- **Utilization**: 30-50%
- **Value**: ✅ Good for prototyping

## Recommendation

**If keeping L40s**: Absolutely scale UP experiments
- Use 1B-7B models
- 5K-10K training samples
- 15-20 epochs
- Proper hyperparameter tuning
- You'll get **publication-quality research**

**If cost-sensitive**: Scale DOWN to 1-2x cheaper GPUs
- RTX 3060/4070 perfectly adequate
- **Save 90%+ on compute**
- Keep current experiment scale

## Quick Win: Hybrid Approach

Run **most experiments** on cheap GPUs, **scale up finals** on L40s:
1. Stages 1-3: RTX 3060 (fast iteration, cheap)
2. Stage 4: L40s (final runs, large models, publication)
3. **Best of both worlds**: Speed + cost efficiency + quality


