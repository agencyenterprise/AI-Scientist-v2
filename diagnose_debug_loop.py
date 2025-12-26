#!/usr/bin/env python3
"""
Diagnostic script to investigate why the coder+reviewer dynamic failed to fix the SDPA error.

This script simulates the debug loop by:
1. Fetching actual error data from MongoDB events
2. Calling the same reviewer function to see what analysis it would generate
3. Showing what prompt the debugger would receive
4. Optionally calling the debug function to see what fix would be generated

Usage:
    python diagnose_debug_loop.py <run_id> [--simulate-fix]
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add AI Scientist to path
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()


def get_sdpa_error_context(run_id: str):
    """Fetch the SDPA error context from MongoDB events."""
    from pymongo import MongoClient
    
    client = MongoClient(os.getenv('MONGODB_URL'))
    db = client['ai-scientist']
    
    # Get events around the SDPA error
    sdpa_events = list(db.events.find({
        'runId': run_id,
        'data.message': {'$regex': 'output_attention|sdpa', '$options': 'i'}
    }).sort('timestamp', 1))
    
    # Reconstruct a representative terminal output that the reviewer would see
    term_output_lines = []
    for event in sdpa_events[:20]:
        msg = event.get('data', {}).get('message', '')
        if msg:
            term_output_lines.append(msg)
    
    return '\n'.join(term_output_lines)


def simulate_reviewer_analysis(term_output: str, code_snippet: str = None):
    """
    Simulate what the reviewer would output given the terminal output.
    Uses the actual review_func_spec from AI Scientist.
    """
    from ai_scientist.treesearch.parallel_agent import review_func_spec
    # Use the main backend query which handles prompt compilation
    from ai_scientist.treesearch.backend import query
    from ai_scientist.treesearch.utils.response import wrap_code
    
    # Construct the same prompt the reviewer uses (mirrors parse_exec_result in parallel_agent.py)
    prompt = {
        "Introduction": (
            "You are an experienced AI researcher. "
            "You have written code for your research experiment and now need to evaluate the output of the code execution. "
            "Analyze the execution output, determine if there were any bugs, and provide a summary of the findings. "
        ),
        "Research idea": "Testing attention head analysis in transformers to detect degeneration patterns",
        "Implementation": wrap_code(code_snippet) if code_snippet else "(code not available)",
        "Execution output": wrap_code(term_output, lang=""),
    }
    
    print("\n" + "="*80)
    print("SIMULATING REVIEWER ANALYSIS")
    print("="*80)
    print("\nPrompt sent to reviewer:")
    print(f"  - Execution output length: {len(term_output)} chars")
    print(f"  - Code snippet length: {len(code_snippet) if code_snippet else 0} chars")
    
    # query returns: (output, req_time, in_tokens, out_tokens, info)
    result = query(
        system_message=prompt,
        user_message=None,
        func_spec=review_func_spec,
        model="gpt-4o",
        temperature=0.3,
    )
    
    # Extract the actual response from the tuple
    response = result[0] if isinstance(result, tuple) else result
    
    print("\nReviewer Response:")
    print(f"  is_bug: {response.get('is_bug', 'N/A')}")
    print(f"  summary: {response.get('summary', 'N/A')}")
    
    return response


def simulate_coder_fix(analysis: str, code: str, term_out: str):
    """
    Simulate what code the coder would generate to fix the bug.
    Uses the actual _debug prompt structure from AI Scientist.
    """
    from ai_scientist.treesearch.backend import query
    from ai_scientist.treesearch.utils.response import wrap_code
    
    # This mirrors the _debug() method in parallel_agent.py
    prompt = {
        "Introduction": (
            "You are an experienced AI researcher. Your previous code for research experiment had a bug, "
            "so based on the information below, you should revise it in order to fix this bug. "
            "Your response should be an implementation outline in natural language,"
            " followed by a single markdown code block which implements the bugfix/solution."
        ),
        "Research idea": "Testing attention head analysis in transformers to detect degeneration patterns",
        "Previous (buggy) implementation": wrap_code(code),
        "Execution output": wrap_code(term_out, lang=""),
        "Bug analysis and suggested fixes": analysis,
        "Instructions": {
            "Response format": (
                "Your response should be a brief outline/sketch of your proposed solution in natural language (3-5 sentences), "
                "followed by a single markdown code block (using the format ```python ... ```) which implements the full code including the bugfix/solution. "
                "Your generated code should be complete and executable. Do not omit any part of the code."
            ),
            "Bugfix improvement sketch guideline": [
                "You should write a brief natural language description (3-5 sentences) of how the issue in the previous implementation can be fixed.",
            ],
        },
    }
    
    print("\nCalling coder LLM to generate fix...")
    
    # Call without function spec to get raw text response
    result = query(
        system_message=prompt,
        user_message=None,
        model="gpt-4o",
        temperature=0.7,
    )
    
    response_text = result[0] if isinstance(result, tuple) else result
    
    print("\n--- CODER'S RESPONSE ---")
    print(response_text[:2500])
    if len(response_text) > 2500:
        print("\n... (truncated)")
    
    # Check if the fix is correct - must be in from_pretrained(), NOT after
    print("\n--- FIX VERIFICATION ---")
    import re
    
    # The CORRECT pattern: attn_implementation in from_pretrained() call
    correct_pattern = r'from_pretrained\s*\([^)]*attn_implementation\s*=\s*["\']eager["\'][^)]*\)'
    
    # The WRONG pattern: setting model.config.attn_implementation after loading
    wrong_pattern = r'model\.config\.attn_implementation\s*=\s*["\']eager["\']'
    
    has_correct = bool(re.search(correct_pattern, response_text))
    has_wrong = bool(re.search(wrong_pattern, response_text))
    
    if has_correct:
        print("✅ CORRECT: attn_implementation='eager' is passed to from_pretrained()")
    elif has_wrong:
        print("❌ WRONG FIX: Setting model.config.attn_implementation AFTER loading doesn't work!")
        print("   The attention layers are already initialized with SDPA when from_pretrained() completes.")
        print("   This explains why the error kept recurring - the 'fix' doesn't actually fix it!")
    elif "attn_implementation" in response_text and "eager" in response_text:
        print("⚠️ UNCLEAR: attn_implementation='eager' mentioned but placement unclear")
    else:
        print("❌ INCORRECT: Fix doesn't include attn_implementation='eager'")


def show_debug_prompt(analysis: str, code: str, term_out: str):
    """Show what the debug prompt would look like."""
    print("\n" + "="*80)
    print("DEBUG PROMPT THAT CODER RECEIVES")
    print("="*80)
    
    # This mirrors _debug() method in parallel_agent.py
    prompt = {
        "Introduction": (
            "You are an experienced AI researcher. Your previous code for research experiment had a bug, "
            "so based on the information below, you should revise it in order to fix this bug. "
            "Your response should be an implementation outline in natural language,"
            " followed by a single markdown code block which implements the bugfix/solution."
        ),
        "Research idea": "Testing attention head analysis in transformers",
        "Previous (buggy) implementation": f"```python\n{code}\n```" if code else "(code not available)",
        "Execution output": f"```\n{term_out}\n```",
        "Bug analysis and suggested fixes": analysis,
    }
    
    print("\nKey sections of the debug prompt:")
    print(f"\n1. Bug analysis and suggested fixes:")
    print(f"   '{analysis}'")
    print(f"\n2. Execution output (truncated):")
    print(f"   '{term_out[:500]}...'")


def analyze_debug_loop_failure(run_id: str, simulate_fix: bool = False):
    """Main analysis function."""
    print("="*80)
    print(f"ANALYZING DEBUG LOOP FOR RUN: {run_id}")
    print("="*80)
    
    # Step 1: Get the error context
    print("\n[1/4] Fetching SDPA error context from MongoDB...")
    term_output = get_sdpa_error_context(run_id)
    
    if not term_output:
        print("  ERROR: No SDPA error events found")
        return
    
    print(f"  Found error context ({len(term_output)} chars)")
    print("\n  Sample error output:")
    print("  " + "-"*60)
    for line in term_output.split('\n')[:10]:
        print(f"  {line}")
    print("  " + "-"*60)
    
    # Step 2: Construct a sample buggy code snippet
    print("\n[2/4] Constructing sample buggy code...")
    sample_buggy_code = '''
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Load model
model = AutoModelForCausalLM.from_pretrained("gpt2-large")
tokenizer = AutoTokenizer.from_pretrained("gpt2-large")

# Enable attention output (THIS CAUSES THE ERROR)
model.config.output_attentions = True

# Run inference
inputs = tokenizer("Hello world", return_tensors="pt")
outputs = model(**inputs, output_attentions=True)
attentions = outputs.attentions
'''
    print("  Sample code that would trigger the error")
    
    # Step 3: Simulate what the reviewer would say
    if simulate_fix:
        print("\n[3/4] Simulating reviewer analysis (calling LLM)...")
        analysis = simulate_reviewer_analysis(term_output, sample_buggy_code)
        
        # Step 4: Show the debug prompt
        print("\n[4/4] Showing debug prompt construction...")
        show_debug_prompt(
            analysis.get('summary', ''),
            sample_buggy_code,
            term_output[:2000]
        )
    else:
        print("\n[3/4] Skipping LLM call (use --simulate-fix to enable)")
        print("\n[4/4] Showing what the analysis SHOULD contain...")
        
        ideal_analysis = (
            "The error 'ValueError: The output_attentions attribute is not supported when using "
            "the attn_implementation set to sdpa' indicates that the model is using SDPA (Scaled "
            "Dot Product Attention) which doesn't support returning attention weights. "
            "FIX: When loading the model, explicitly set attn_implementation='eager' to use the "
            "standard attention implementation that supports output_attentions=True. "
            "Example: model = AutoModelForCausalLM.from_pretrained('gpt2-large', attn_implementation='eager')"
        )
        
        print(f"\n  IDEAL analysis that should be generated:")
        print(f"  '{ideal_analysis}'")
    
    # Step 5: Optionally simulate what the coder would generate
    if simulate_fix:
        print("\n" + "="*80)
        print("SIMULATING CODER FIX ATTEMPT")
        print("="*80)
        simulate_coder_fix(analysis.get('summary', ''), sample_buggy_code, term_output[:2000])
    
    # Summary of the problem
    print("\n" + "="*80)
    print("ROOT CAUSE ANALYSIS")
    print("="*80)
    
    print("""
🔍 ROOT CAUSE IDENTIFIED: LLM generates plausible but INCORRECT fix

1. THE ERROR MESSAGE:
   "The `output_attentions` attribute is not supported when using the `attn_implementation` 
   set to sdpa. Please set it to 'eager' instead."

2. WHAT THE LLM DOES (WRONG):
   model = AutoModelForCausalLM.from_pretrained("gpt2-large")  # Loaded with SDPA
   model.config.attn_implementation = 'eager'  # TOO LATE! Doesn't reinitialize attention layers
   model.config.output_attentions = True  # Still fails because model still uses SDPA internally

3. WHAT SHOULD BE DONE (CORRECT):
   model = AutoModelForCausalLM.from_pretrained("gpt2-large", attn_implementation='eager')

4. WHY THE LLM GETS IT WRONG:
   - The error message says "set it to 'eager'" but doesn't specify WHERE
   - Setting model.config.attn_implementation AFTER loading looks plausible but doesn't work
   - The attention layers are instantiated during from_pretrained(), not when config changes
   - This is a subtle HuggingFace Transformers behavior that LLMs don't fully understand

5. SYSTEMIC ISSUE IN AI SCIENTIST:
   - The reviewer and coder both fall for this plausible-but-wrong fix
   - Each debugging iteration generates the same broken fix
   - The tree search has no way to learn from repeated failures of the same fix pattern

6. RECOMMENDED FIXES FOR AI SCIENTIST:
   a) Add few-shot examples of correct HuggingFace patterns to the prompt
   b) Include "attn_implementation must be passed to from_pretrained()" in guidance
   c) Track recurring error patterns and inject them as explicit warnings
   d) Add domain-specific knowledge about common PyTorch/HuggingFace gotchas
""")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diagnose_debug_loop.py <run_id> [--simulate-fix]")
        print("\nExample:")
        print("  python diagnose_debug_loop.py f7e1c42f-27b5-4f72-9c4e-fa1a4f49270d")
        print("  python diagnose_debug_loop.py f7e1c42f-27b5-4f72-9c4e-fa1a4f49270d --simulate-fix")
        sys.exit(1)
    
    run_id = sys.argv[1]
    simulate_fix = "--simulate-fix" in sys.argv
    
    analyze_debug_loop_failure(run_id, simulate_fix)

