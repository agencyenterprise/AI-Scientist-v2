#!/usr/bin/env python3
"""
Manual script to run writeup for an experiment that completed but failed during paper generation.
Usage: python manual_writeup.py <experiment_directory>
"""

import sys
import os
import yaml
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: python manual_writeup.py <experiment_directory>")
    print("\nExample:")
    print("  python manual_writeup.py experiments/2025-10-23_12-57-41_crystal_llms_run_349fca1e-1e8c-4992-8fc3-f38c644c0aee")
    sys.exit(1)

experiment_dir = sys.argv[1]

if not os.path.exists(experiment_dir):
    print(f"❌ Experiment directory not found: {experiment_dir}")
    sys.exit(1)

print(f"📁 Running writeup for: {experiment_dir}")

with open("bfts_config.yaml", 'r') as f:
    config = yaml.safe_load(f)

plot_model = config.get("writeup", {}).get("plot_model", "gpt-5.1")
small_model = config.get("writeup", {}).get("small_model", "gpt-5.1")
big_model = config.get("writeup", {}).get("big_model", "gpt-5.1")

print(f"✓ Models: plot={plot_model}, small={small_model}, big={big_model}")

exp_results_dir = os.path.join(experiment_dir, "logs/0-run/experiment_results")
if os.path.exists(exp_results_dir):
    import shutil
    dest_dir = os.path.join(experiment_dir, "experiment_results")
    if os.path.exists(dest_dir):
        print(f"⚠️  Removing existing experiment_results directory")
        shutil.rmtree(dest_dir)
    print(f"📦 Copying experiment results...")
    shutil.copytree(exp_results_dir, dest_dir, dirs_exist_ok=True)

print("\n📊 Aggregating plots...")
from ai_scientist.perform_plotting import aggregate_plots
aggregate_plots(base_folder=experiment_dir, model=plot_model)

print("\n📄 Gathering citations...")
from ai_scientist.perform_icbinb_writeup import gather_citations, perform_writeup

citations_text = gather_citations(
    experiment_dir,
    num_cite_rounds=15,
    small_model=small_model
)

print("\n✍️  Writing paper...")
writeup_success = perform_writeup(
    base_folder=experiment_dir,
    big_model=big_model,
    page_limit=4,
    citations_text=citations_text
)

if writeup_success:
    pdf_files = [f for f in os.listdir(experiment_dir) if f.endswith(".pdf")]
    if pdf_files:
        print(f"\n✅ Paper generated successfully: {pdf_files[0]}")
        print(f"   Location: {os.path.join(experiment_dir, pdf_files[0])}")
    else:
        print("\n⚠️  Writeup completed but no PDF found")
else:
    print("\n❌ Writeup failed")

exp_results_cleanup = os.path.join(experiment_dir, "experiment_results")
if os.path.exists(exp_results_cleanup):
    import shutil
    shutil.rmtree(exp_results_cleanup)
    print("\n🧹 Cleaned up experiment_results directory")

print("\n✨ Done!")


