#!/bin/bash
set -e  # Exit on any error

echo "=== Starting RunPod Initialization ==="

# Step 1: Download and Install Anaconda (if not already installed)
if [ ! -d ~/anaconda3 ]; then
    echo "Step 1: Downloading Anaconda..."
    curl -o ~/Anaconda3-2025.06-0-Linux-x86_64.sh https://repo.anaconda.com/archive/Anaconda3-2025.06-0-Linux-x86_64.sh
    
    echo "Step 2: Installing Anaconda in batch mode..."
    bash ~/Anaconda3-2025.06-0-Linux-x86_64.sh -b -p ~/anaconda3
    
    echo "Step 3: Initializing conda..."
    ~/anaconda3/bin/conda init bash
else
    echo "Step 1-3: Anaconda already installed at ~/anaconda3, skipping installation..."
fi

# Step 4: Source bashrc to activate conda
echo "Step 4: Sourcing bashrc..."
source ~/.bashrc

# Enable HuggingFace fast transfer for faster dataset downloads
export HF_HUB_ENABLE_HF_TRANSFER=1

# Step 6: Accept Anaconda Terms of Service (if not already accepted)
echo "Step 6: Accepting Anaconda Terms of Service..."
~/anaconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main 2>/dev/null || true
~/anaconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r 2>/dev/null || true

# Step 7: Create conda environment (or skip if exists)
if ~/anaconda3/bin/conda env list | grep -q "^ai_scientist "; then
    echo "Step 7: conda environment 'ai_scientist' already exists, skipping creation..."
else
    echo "Step 7: Creating conda environment ai_scientist..."
    ~/anaconda3/bin/conda create -n ai_scientist python=3.11 -y
fi

# Step 8: Activate the environment
echo "Step 8: Activating ai_scientist environment..."
source ~/anaconda3/bin/activate ai_scientist

# Step 9: Install PDF and LaTeX tools (before PyTorch to avoid conflicts)
echo "Step 9: Installing PDF and LaTeX tools..."
conda install -y anaconda::poppler
conda install -y conda-forge::chktex

# Step 10: Install Python package requirements (except PyTorch)
echo "Step 10: Installing Python requirements (excluding torch packages)..."
pip install -r requirements.txt --no-deps || true
pip install -r requirements.txt

# Step 11: Install PyTorch with CUDA support via pip (avoids Intel MKL conflicts)
echo "Step 11: Detecting GPU and installing appropriate PyTorch version..."

# Check if GPU is RTX 5090 or other Blackwell (sm_120+) architecture
GPU_CHECK=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)

if [[ "$GPU_CHECK" =~ "RTX 5090" ]] || [[ "$GPU_CHECK" =~ "RTX 50" ]]; then
    echo "  Detected Blackwell GPU ($GPU_CHECK) - Installing PyTorch nightly with sm_120 support..."
    pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu121
else
    echo "  Installing stable PyTorch with CUDA 12.1 support..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
fi

# Step 12: Install anthropic
echo "Step 12: Installing anthropic..."
pip install anthropic

# Step 13: Install LaTeX and related system packages
echo "Step 13: Installing LaTeX and system packages..."
apt-get update && apt-get install -y texlive-latex-base texlive-latex-extra texlive-fonts-recommended texlive-bibtex-extra biber poppler-utils chktex screen

# Step 14: Configure automatic conda environment activation and persist env vars
echo "Step 14: Configuring auto-activation of ai_scientist environment..."

# Remove old AI Scientist config if it exists
sed -i '/# Auto-activate ai_scientist conda environment/,/# End AI Scientist config/d' ~/.bashrc

# Add fresh config to bashrc
cat >> ~/.bashrc << 'BASHRC_EOF'

# Auto-activate ai_scientist conda environment
if [ -f ~/anaconda3/etc/profile.d/conda.sh ]; then
    . ~/anaconda3/etc/profile.d/conda.sh
    conda activate ai_scientist
fi

# AI Scientist environment variables
BASHRC_EOF

# Add environment variables from .env to bashrc
if [ -f .env ]; then
    echo "# Environment variables from .env" >> ~/.bashrc
    while IFS= read -r line; do
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
            # Add export to bashrc
            echo "export $line" >> ~/.bashrc
        fi
    done < .env
fi

echo "export HF_HUB_ENABLE_HF_TRANSFER=1" >> ~/.bashrc
echo "# End AI Scientist config" >> ~/.bashrc

echo "✓ Auto-activation and environment variables configured in ~/.bashrc"

echo ""
echo "=== RunPod Initialization Complete ==="
echo ""
echo "✅ Conda environment: ai_scientist (active)"
echo "✅ Environment variables: Saved to ~/.bashrc"
echo "✅ Auto-activation: Configured for all future shells"
echo ""
echo "Current environment variables:"
echo "  OPENAI_API_KEY: ${OPENAI_API_KEY:0:10}..." 
echo "  MONGODB_URL: ${MONGODB_URL:0:20}..."
echo ""

# Step 15: GPU and PyTorch CUDA compatibility check
echo "=== GPU and PyTorch CUDA Compatibility Check ==="
echo ""
python << 'PYTHON_EOF'
import subprocess
import re
import sys

print("Checking GPU information...")
result = subprocess.run(['nvidia-smi', '--query-gpu=name,compute_cap', '--format=csv,noheader'], 
                       capture_output=True, text=True)

if result.returncode == 0:
    print('\n📊 Available GPUs:')
    print(result.stdout)
    
    # Extract compute capability and check compatibility
    has_warning = False
    for line in result.stdout.strip().split('\n'):
        match = re.search(r'(\d+\.\d+)', line)
        if match:
            cc = float(match.group(1))
            if cc < 6.0:
                print(f'\n⚠️  WARNING: Compute capability {cc} may not be supported by CUDA 12.1')
                print('   Recommended action: Use CUDA 11.8 instead')
                print('   Edit init_runpod.sh line 73 to use: --index-url https://download.pytorch.org/whl/cu118')
                has_warning = True
    
    if not has_warning:
        print('\n✅ GPU compute capability appears compatible with CUDA 12.1')
else:
    print('\n❌ Could not query GPU info')
    sys.exit(0)

print('\n🔍 Checking PyTorch CUDA setup...')
try:
    import torch
    print(f'PyTorch version: {torch.__version__}')
    print(f'CUDA available: {torch.cuda.is_available()}')
    print(f'CUDA version (PyTorch): {torch.version.cuda}')
    print(f'Number of GPUs: {torch.cuda.device_count()}')
    
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            print(f'GPU {i}: {torch.cuda.get_device_name(i)}')
        
        # Test a simple CUDA operation
        print('\n🧪 Testing CUDA with a simple operation...')
        try:
            x = torch.randn(10, 10, device='cuda')
            y = x * x
            _ = y.sum().item()
            print('✅ CUDA test passed - GPU is working correctly!')
        except Exception as e:
            print(f'❌ CUDA test FAILED: {e}')
            print('\n🔧 Troubleshooting:')
            print('   1. Try reinstalling PyTorch with CUDA 11.8:')
            print('      pip uninstall torch torchvision torchaudio')
            print('      pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118')
            print('   2. Or force CPU usage by setting: CUDA_VISIBLE_DEVICES=""')
    else:
        print('⚠️  CUDA not available in PyTorch')
except ImportError:
    print('❌ PyTorch not installed yet')

print('')
PYTHON_EOF

echo "=== End of GPU Check ==="
echo ""

# Step 16: Reload bashrc to ensure all env vars are available
echo "Step 16: Reloading environment..."
source ~/.bashrc

# Step 17: Start the pod worker
echo ""
echo "=== Starting Pod Worker ==="
echo ""
echo "🤖 Launching AI Scientist pod worker..."
echo "   This will poll MongoDB for queued experiments and run them automatically."
echo "   Press Ctrl+C to stop the worker gracefully."
echo ""
echo "   If you need to restart later, just run: python pod_worker.py"
echo "   (no need to source bashrc - it's automatic!)"
echo ""

# Use exec to replace this shell process with the Python process
# This makes pod_worker.py a top-level process, not a subprocess
# Benefits: proper signal handling, clean process tree, no orphaned shells
exec python pod_worker.py
