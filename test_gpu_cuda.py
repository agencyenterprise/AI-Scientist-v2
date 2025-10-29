#!/usr/bin/env python3
"""
GPU and PyTorch CUDA Compatibility Test Script
Run this on your RunPod instance to diagnose CUDA issues
"""

import subprocess
import re
import sys

def check_gpu_info():
    """Check GPU compute capability"""
    print("=" * 60)
    print("📊 GPU INFORMATION CHECK")
    print("=" * 60)
    
    result = subprocess.run(
        ['nvidia-smi', '--query-gpu=name,compute_cap,driver_version,cuda_version', '--format=csv'],
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        print("\n✅ nvidia-smi output:")
        print(result.stdout)
        
        # Parse compute capability
        lines = result.stdout.strip().split('\n')[1:]  # Skip header
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 2:
                gpu_name = parts[0].strip()
                cc_str = parts[1].strip()
                match = re.search(r'(\d+\.\d+)', cc_str)
                if match:
                    cc = float(match.group(1))
                    print(f"\n🔍 GPU: {gpu_name}")
                    print(f"🔍 Compute Capability: {cc}")
                    
                    if cc < 6.0:
                        print(f"\n⚠️  WARNING: Compute capability {cc} is OLD")
                        print("   CUDA 12.1 may not support this GPU")
                        print("   Recommendation: Use CUDA 11.8 or CPU")
                    elif cc >= 6.0 and cc < 7.0:
                        print(f"\n✅ Compute capability {cc} - Pascal architecture")
                        print("   Should work with CUDA 12.1")
                    elif cc >= 7.0 and cc < 8.0:
                        print(f"\n✅ Compute capability {cc} - Volta/Turing architecture")
                        print("   Fully compatible with CUDA 12.1")
                    else:
                        print(f"\n✅ Compute capability {cc} - Ampere/Ada architecture")
                        print("   Fully compatible with CUDA 12.1")
                    
                    return cc
    else:
        print("\n❌ Could not run nvidia-smi")
        print("   Are you on a GPU instance?")
        return None

def check_pytorch():
    """Check PyTorch CUDA setup"""
    print("\n" + "=" * 60)
    print("🔍 PYTORCH CUDA CHECK")
    print("=" * 60)
    
    try:
        import torch
        print(f"\n✅ PyTorch installed")
        print(f"   Version: {torch.__version__}")
        print(f"   CUDA available: {torch.cuda.is_available()}")
        print(f"   CUDA version (built with): {torch.version.cuda}")
        print(f"   cuDNN version: {torch.backends.cudnn.version()}")
        print(f"   Number of GPUs: {torch.cuda.device_count()}")
        
        compute_cap = None
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                name = torch.cuda.get_device_name(i)
                print(f"   GPU {i}: {name}")
                
                # Try to get compute capability from PyTorch
                if compute_cap is None:
                    try:
                        major, minor = torch.cuda.get_device_capability(i)
                        compute_cap = float(f"{major}.{minor}")
                        print(f"   Compute capability: sm_{major}{minor} ({compute_cap})")
                        
                        # Special warning for sm_120
                        if compute_cap >= 12.0:
                            print(f"   ⚠️  WARNING: sm_120 is not supported by any PyTorch build yet!")
                            print(f"   ⚠️  Even PyTorch nightly doesn't have sm_120 kernels.")
                    except:
                        pass
        
        return torch, compute_cap
    except ImportError:
        print("\n❌ PyTorch not installed")
        return None, None

def test_cuda_operations(torch):
    """Run actual CUDA operations to test if kernels work"""
    print("\n" + "=" * 60)
    print("🧪 CUDA OPERATION TESTS")
    print("=" * 60)
    
    if not torch.cuda.is_available():
        print("\n⚠️  CUDA not available, skipping tests")
        return False
    
    all_passed = True
    
    # Test 1: Simple tensor operation
    print("\n[Test 1] Simple tensor multiplication...")
    try:
        x = torch.randn(100, 100, device='cuda')
        y = x * x
        result = y.sum().item()
        print(f"   ✅ PASSED - Result: {result:.2f}")
    except Exception as e:
        print(f"   ❌ FAILED - {type(e).__name__}: {e}")
        all_passed = False
    
    # Test 2: Matrix multiplication
    print("\n[Test 2] Matrix multiplication (matmul)...")
    try:
        a = torch.randn(500, 500, device='cuda')
        b = torch.randn(500, 500, device='cuda')
        c = torch.matmul(a, b)
        torch.cuda.synchronize()
        print(f"   ✅ PASSED - Output shape: {c.shape}")
    except Exception as e:
        print(f"   ❌ FAILED - {type(e).__name__}: {e}")
        all_passed = False
    
    # Test 3: RNN/LSTM (common failure point with cuDNN)
    print("\n[Test 3] LSTM (cuDNN test)...")
    try:
        import torch.nn as nn
        lstm = nn.LSTM(input_size=10, hidden_size=20, num_layers=2).cuda()
        input_seq = torch.randn(5, 3, 10).cuda()  # seq_len, batch, input_size
        output, (hn, cn) = lstm(input_seq)
        torch.cuda.synchronize()
        print(f"   ✅ PASSED - Output shape: {output.shape}")
    except Exception as e:
        print(f"   ❌ FAILED - {type(e).__name__}: {e}")
        print(f"   This is the error you saw in your experiment!")
        all_passed = False
    
    # Test 4: Transformer (GPT-2 style attention)
    print("\n[Test 4] Multi-head attention...")
    try:
        import torch.nn as nn
        attn = nn.MultiheadAttention(embed_dim=64, num_heads=8).cuda()
        query = torch.randn(10, 2, 64).cuda()
        output, weights = attn(query, query, query)
        torch.cuda.synchronize()
        print(f"   ✅ PASSED - Output shape: {output.shape}")
    except Exception as e:
        print(f"   ❌ FAILED - {type(e).__name__}: {e}")
        all_passed = False
    
    return all_passed

def print_recommendations(all_tests_passed, compute_cap):
    """Print recommendations based on test results"""
    print("\n" + "=" * 60)
    print("💡 RECOMMENDATIONS")
    print("=" * 60)
    
    if all_tests_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("   Your GPU and PyTorch CUDA setup is working correctly.")
        print("   The AI Scientist experiments should run on GPU without issues.")
    else:
        print("\n⚠️  SOME TESTS FAILED")
        
        # Check for RTX 5090 / Blackwell architecture (sm_120)
        if compute_cap and compute_cap >= 12.0:
            print("\n🚀 DETECTED: RTX 5090 or newer Blackwell GPU (sm_120)")
            print("   Your GPU is TOO NEW - NO PyTorch build supports sm_120 yet!")
            print("   (Not even nightly builds as of Nov 2024)")
            print("\n⭐ RECOMMENDED SOLUTION: Switch to a different GPU on RunPod")
            print("   Request a pod with one of these fully-supported GPUs:")
            print("   - RTX 4090 (sm_89) ✅ Excellent performance, stable")
            print("   - A100 (sm_80) ✅ Best for ML workloads, very stable")
            print("   - RTX 3090 (sm_86) ✅ Good value, fully supported")
            print("\n   These will give you better stability and are fully supported by PyTorch.")
            print("\n💡 Alternative (temporary): Force CPU mode")
            print("   export CUDA_VISIBLE_DEVICES=\"\"")
            print("   Then rerun experiments (will be slower but will work)")
            print("\n⏳ Waiting for PyTorch sm_120 support: Probably weeks/months away")
        else:
            print("\n🔧 Troubleshooting steps:")
            print("\n1. Try PyTorch with CUDA 11.8 (broader GPU support):")
            print("   pip uninstall torch torchvision torchaudio -y")
            print("   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
            
            print("\n2. If that doesn't work, try disabling cuDNN:")
            print("   Add to your Python code:")
            print("   import torch")
            print("   torch.backends.cudnn.enabled = False")
            
            print("\n3. If still failing, force CPU mode:")
            print("   export CUDA_VISIBLE_DEVICES=\"\"")
            print("   (Then restart your experiment)")
            
            if compute_cap and compute_cap < 6.0:
                print("\n⚠️  NOTE: Your GPU is quite old (compute capability < 6.0)")
                print("   Modern PyTorch may not support it well.")
                print("   Consider requesting a newer GPU on RunPod.")

def main():
    print("\n" + "=" * 60)
    print("🚀 GPU AND PYTORCH CUDA COMPATIBILITY TEST")
    print("=" * 60)
    print("\nThis script will diagnose why your experiments are falling back to CPU")
    print()
    
    # Check GPU (from nvidia-smi)
    compute_cap_nvidia = check_gpu_info()
    
    # Check PyTorch (returns compute_cap from PyTorch API)
    torch, compute_cap_torch = check_pytorch()
    
    # Use PyTorch compute cap if available, otherwise nvidia-smi
    compute_cap = compute_cap_torch if compute_cap_torch is not None else compute_cap_nvidia
    
    # Run CUDA tests
    if torch:
        all_passed = test_cuda_operations(torch)
    else:
        all_passed = False
    
    # Print recommendations
    print_recommendations(all_passed, compute_cap)
    
    print("\n" + "=" * 60)
    print("✅ TEST COMPLETE")
    print("=" * 60)
    print()

if __name__ == "__main__":
    main()

