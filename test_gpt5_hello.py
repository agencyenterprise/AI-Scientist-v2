#!/usr/bin/env python3
"""Quick test to verify gpt-5.1 is working with code generation."""

import os
from dotenv import load_dotenv
load_dotenv()

from ai_scientist.llm import create_client, get_response_from_llm

def main():
    print("=" * 60)
    print("Testing gpt-5.1 with code generation prompt")
    print("=" * 60)
    
    client, model = create_client("gpt-5.1")
    
    system_message = """You are an AI researcher writing Python code for machine learning experiments.
Your code should be complete, runnable, and save results as numpy arrays.

CRITICAL: Your code MUST save experiment data using:
np.save(os.path.join(working_dir, 'experiment_data.npy'), experiment_data)
"""

    prompt = """Write a complete Python script that:
1. Loads a small Qwen model (Qwen/Qwen2-0.5B) for text generation
2. Fine-tunes it on a tiny synthetic dataset (just 10 examples of "Q: ... A: ..." pairs)
3. Runs inference before and after fine-tuning to show the difference
4. Saves training metrics (loss per step) to experiment_data.npy

The code should be self-contained, use HuggingFace transformers, and complete quickly.
Include working_dir = os.path.join(os.getcwd(), 'working') at the start.
"""

    print(f"\nPrompt:\n{prompt}\n")
    print("-" * 60)
    print("Calling gpt-5.1...")
    
    try:
        response, history = get_response_from_llm(
            prompt=prompt,
            client=client,
            model=model,
            system_message=system_message,
            print_debug=False,
            temperature=1.0,  # gpt-5 only supports temp=1
        )
        
        print("\n" + "=" * 60)
        print("RESPONSE FROM gpt-5.1:")
        print("=" * 60)
        print(response)
        
        # Check if it includes the critical np.save line
        if "np.save" in response and "experiment_data" in response:
            print("\n✅ Response includes np.save for experiment_data!")
        else:
            print("\n⚠️ WARNING: Response may be missing np.save for experiment_data")
            
        print("\n✅ gpt-5.1 is working!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

