#!/usr/bin/env python3
"""
Test the robustness fixes for filter_experiment_summaries and load_exp_summaries.
"""

import sys
import json
import tempfile
import os
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from ai_scientist.perform_icbinb_writeup import (
    load_exp_summaries,
    filter_experiment_summaries,
)


def test_filter_with_none_values():
    """Test that filter_experiment_summaries handles None values gracefully."""
    print("Testing filter_experiment_summaries with None values...")
    
    # Test case 1: Stage summary is None
    exp_summaries = {
        "BASELINE_SUMMARY": None,
        "RESEARCH_SUMMARY": {"best node": {"analysis": "test"}},
        "ABLATION_SUMMARY": []
    }
    
    result = filter_experiment_summaries(exp_summaries, "plot_aggregation")
    print("✓ Handled None stage summary without crashing")
    
    # Test case 2: Nested None value
    exp_summaries = {
        "BASELINE_SUMMARY": {"best node": None},
        "RESEARCH_SUMMARY": {"best node": {"analysis": "test"}},
    }
    
    result = filter_experiment_summaries(exp_summaries, "plot_aggregation")
    print("✓ Handled nested None value without crashing")
    
    # Test case 3: Unknown stage names
    exp_summaries = {
        "SOME_NEW_STAGE": {"best node": {"analysis": "test"}},
        "ANOTHER_STAGE": {"best node": {"plot_plan": "test"}},
    }
    
    result = filter_experiment_summaries(exp_summaries, "plot_aggregation")
    print("✓ Handled unknown stage names without crashing")
    
    # Test case 4: Unknown step name (should warn, not crash)
    exp_summaries = {
        "BASELINE_SUMMARY": {"best node": {"analysis": "test"}},
    }
    
    result = filter_experiment_summaries(exp_summaries, "unknown_step")
    print("✓ Handled unknown step name without crashing")
    
    # Test case 5: Empty exp_summaries
    result = filter_experiment_summaries({}, "plot_aggregation")
    print("✓ Handled empty exp_summaries without crashing")
    
    # Test case 6: None exp_summaries
    result = filter_experiment_summaries(None, "plot_aggregation")
    print("✓ Handled None exp_summaries without crashing")
    
    print("\n✅ All filter_experiment_summaries tests passed!")


def test_load_with_null_json():
    """Test that load_exp_summaries handles null JSON values gracefully."""
    print("\nTesting load_exp_summaries with null JSON files...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test directory structure
        logs_dir = os.path.join(tmpdir, "logs", "0-run")
        os.makedirs(logs_dir, exist_ok=True)
        
        # Create JSON file with null
        baseline_path = os.path.join(logs_dir, "baseline_summary.json")
        with open(baseline_path, "w") as f:
            json.dump(None, f)
        
        # Create valid JSON file
        research_path = os.path.join(logs_dir, "research_summary.json")
        with open(research_path, "w") as f:
            json.dump({"best node": {"analysis": "test"}}, f)
        
        # Don't create ablation_summary.json to test missing file
        
        # Load summaries
        summaries = load_exp_summaries(tmpdir)
        
        # Verify results
        assert summaries["BASELINE_SUMMARY"] == {}, "Should return empty dict for null JSON"
        assert summaries["RESEARCH_SUMMARY"]["best node"]["analysis"] == "test"
        assert summaries["ABLATION_SUMMARY"] == [], "Should return empty list for missing ablation file"
        
        print("✓ Handled null JSON value correctly")
        print("✓ Handled missing file correctly")
        print("✓ Handled valid JSON correctly")
        
        print("\n✅ All load_exp_summaries tests passed!")


def test_integration():
    """Test the full pipeline: load -> filter."""
    print("\nTesting integration: load -> filter...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = os.path.join(tmpdir, "logs", "0-run")
        os.makedirs(logs_dir, exist_ok=True)
        
        # Create files with various edge cases
        baseline_path = os.path.join(logs_dir, "baseline_summary.json")
        with open(baseline_path, "w") as f:
            json.dump(None, f)  # null JSON
        
        research_path = os.path.join(logs_dir, "research_summary.json")
        with open(research_path, "w") as f:
            json.dump({
                "best node": {
                    "analysis": "test analysis",
                    "plot_plan": "test plan",
                    "overall_plan": "test overall"
                }
            }, f)
        
        # Load and filter
        summaries = load_exp_summaries(tmpdir)
        filtered = filter_experiment_summaries(summaries, "plot_aggregation")
        
        # Verify filtering worked
        assert "BASELINE_SUMMARY" not in filtered or filtered["BASELINE_SUMMARY"] == {}
        assert "RESEARCH_SUMMARY" in filtered
        assert "analysis" in filtered["RESEARCH_SUMMARY"]["best node"]
        assert "plot_plan" in filtered["RESEARCH_SUMMARY"]["best node"]
        
        print("✓ Integration test passed: null files handled, valid data filtered correctly")
        
        print("\n✅ All integration tests passed!")


if __name__ == "__main__":
    try:
        test_filter_with_none_values()
        test_load_with_null_json()
        test_integration()
        
        print("\n" + "="*60)
        print("🎉 ALL TESTS PASSED! The robustness fixes work correctly.")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

