import os
import sys
import json
import shlex
import subprocess
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[2]

IDEAS_DIR = ROOT / "ai_scientist" / "ideas"
EXPERIMENTS_DIR = ROOT / "experiments"

# Conda environment Python (has torch and all dependencies)
CONDA_PYTHON = "/opt/homebrew/anaconda3/envs/ai_scientist/bin/python"


def list_ideas() -> List[Path]:
    IDEAS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(IDEAS_DIR.glob("*.md"))


def create_idea_file(
    filename: str, title: str, keywords: List[str], tldr: str, abstract: str
) -> Path:
    filename = filename if filename.endswith(".md") else f"{filename}.md"
    path = IDEAS_DIR / filename
    if path.exists():
        raise FileExistsError(f"Idea file already exists: {path}")
    content = [
        f"# Title\n{title}\n",
        f"\n# Keywords\n{', '.join(keywords)}\n",
        f"\n# TL;DR\n{tldr}\n",
        f"\n# Abstract\n{abstract}\n",
    ]
    path.write_text("\n".join(content))
    return path


def list_experiments() -> List[Path]:
    if not EXPERIMENTS_DIR.exists():
        return []
    return [p for p in EXPERIMENTS_DIR.iterdir() if p.is_dir()]


def experiments_for_idea(idea_filename: str) -> List[Path]:
    """Return experiment dirs that contain this idea name in their folder name."""
    if not EXPERIMENTS_DIR.exists():
        return []
    stem = Path(idea_filename).stem
    return [p for p in EXPERIMENTS_DIR.iterdir() if p.is_dir() and stem in p.name]


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _read_stage_notes(run_dir: Path) -> List[Dict]:
    """Read per-stage info from logs/0-run/stage_*/notes.

    run_dir is logs/0-run.
    """
    stages: List[Dict] = []
    if not run_dir.exists():
        return stages
    for stage_dir in sorted(run_dir.glob("stage_*")):
        notes_dir = stage_dir / "notes"
        if not notes_dir.exists():
            continue
        stage_info = {"path": str(notes_dir)}
        prog = _read_json(notes_dir / "stage_progress.json")
        if prog:
            stage_info.update(
                {
                    "name": prog.get("stage"),
                    "total_nodes": prog.get("total_nodes"),
                    "buggy_nodes": prog.get("buggy_nodes"),
                    "good_nodes": prog.get("good_nodes"),
                    "best_metric": prog.get("best_metric"),
                    "notes": prog.get("current_findings"),
                }
            )
        # Latest node summary if available
        node_summaries = sorted(notes_dir.glob("node_*_summary.json"))
        if node_summaries:
            try:
                stage_info["latest_node_summary"] = _read_json(node_summaries[-1])
            except Exception:
                stage_info["latest_node_summary"] = None
        stages.append(stage_info)
    return stages


def read_experiment_status(exp_dir: Path) -> Dict:
    """Summarize status from logs/0-run directory."""
    logs_dir = exp_dir / "logs" / "0-run"
    status: Dict = {
        "stage_summary": "Pending...",
        "progress_ratio": None,
        "total_nodes": 0,
        "good_nodes": 0,
        "buggy_nodes": 0,
        "stages": [],
        "current_stage": None,
    }
    if not logs_dir.exists():
        return status

    # Stage summaries from completed/saved stage notes
    stages = _read_stage_notes(logs_dir)
    
    # Also check for stage folders even if notes don't exist yet
    all_stage_dirs = sorted(logs_dir.glob("stage_*"))
    stage_names_from_dirs = [d.name.replace("stage_", "") for d in all_stage_dirs]
    
    # If we have more stage dirs than stage notes, add placeholders for active stages
    if len(all_stage_dirs) > len(stages):
        for stage_dir in all_stage_dirs[len(stages):]:
            stage_name = stage_dir.name.replace("stage_", "")
            stages.append({
                "name": stage_name,
                "total_nodes": 0,
                "good_nodes": 0,
                "buggy_nodes": 0,
                "best_metric": "Running...",
                "notes": "Stage in progress - notes not saved yet",
                "path": str(stage_dir),
            })
    
    status["stages"] = stages
    if stages:
        last = stages[-1]
        status["stage_summary"] = f"{last.get('name','stage')} - Good: {last.get('good_nodes',0)} / Buggy: {last.get('buggy_nodes',0)}"
        status["total_nodes"] = last.get("total_nodes", 0)
        status["good_nodes"] = last.get("good_nodes", 0)
        status["buggy_nodes"] = last.get("buggy_nodes", 0)
        status["current_stage"] = last.get("name")

    # Estimate progress by comparing number of stage folders to 4 stages
    completed_stage_count = len(stages)
    status["progress_ratio"] = min(1.0, completed_stage_count / 4.0) if stages else 0.0

    return status


def read_experiment_artifacts(exp_dir: Path) -> Dict:
    logs_dir = exp_dir / "logs" / "0-run"
    artifacts = {
        "figures": [],
        "experiment_plots": [],  # Real-time plots from experiment_results
        "pdf": None,
        "tree_html": None,
    }
    
    # Real-time experiment plots (generated during runs)
    exp_results_dir = logs_dir / "experiment_results"
    if exp_results_dir.exists():
        for exp_folder in sorted(exp_results_dir.glob("experiment_*")):
            plots = sorted(exp_folder.glob("*.png"))
            artifacts["experiment_plots"].extend(plots)
    
    # Final aggregated figures (created at the end)
    figs_dir = exp_dir / "figures"
    if figs_dir.exists():
        artifacts["figures"] = sorted(figs_dir.glob("*.png"))
    
    # PDF
    pdfs = sorted([p for p in exp_dir.glob("*.pdf") if "reflection" not in p.name])
    if pdfs:
        artifacts["pdf"] = pdfs[-1]
    
    # Tree visualization: use latest stage dir
    stage_dirs = sorted(logs_dir.glob("stage_*"))
    if stage_dirs:
        latest_stage = stage_dirs[-1]
        tree_html = latest_stage / "tree_plot.html"
        if tree_html.exists():
            artifacts["tree_html"] = tree_html
    
    # Also check for unified tree viz
    unified_tree = logs_dir / "unified_tree_viz.html"
    if unified_tree.exists():
        artifacts["tree_html"] = unified_tree
        
    return artifacts


def spawn_ideation(
    workshop_file: str,
    model: str = "gpt-5",
    max_num_generations: int = 20,
    num_reflections: int = 5,
):
    """Run ideation script in background to generate ideas JSON from a .md file."""
    # Use conda Python (has all dependencies)
    py = CONDA_PYTHON if Path(CONDA_PYTHON).exists() else sys.executable
    log_name = f"ideation_{Path(workshop_file).stem}"
    log_file = f"/tmp/{log_name}.log"
    
    cmd = [
        py,
        str(ROOT / "ai_scientist" / "perform_ideation_temp_free.py"),
        "--workshop-file",
        workshop_file,
        "--model",
        model,
        "--max-num-generations",
        str(max_num_generations),
        "--num-reflections",
        str(num_reflections),
    ]
    
    with open(log_file, "w") as log:
        subprocess.Popen(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)


def spawn_pipeline(
    idea_json_path: str,
    writeup_type: str,
    add_dataset_ref: bool,
    load_code: bool,
    attempt_id: int,
    model_writeup: str,
    model_citation: str,
    model_review: str,
    model_agg_plots: str,
    num_cite_rounds: int,
):
    """Start pipeline in background. If given a .md (no .json yet), first run ideation then launch.
    idea_json_path may be a .json (existing) or a .md; we'll route accordingly.
    """
    path = Path(idea_json_path)
    # Use conda Python (has torch and all dependencies)
    py = CONDA_PYTHON if Path(CONDA_PYTHON).exists() else sys.executable
    
    if path.suffix == ".json" and path.exists():
        # Directly launch using conda Python
        log_name = f"pipeline_{path.stem}_attempt_{attempt_id}"
        log_file = f"/tmp/{log_name}.log"
        
        cmd = [
            py,
            str(ROOT / "launch_scientist_bfts.py"),
            "--load_ideas",
            str(path),
            "--writeup-type",
            writeup_type,
            "--attempt_id",
            str(attempt_id),
            "--model_writeup",
            model_writeup,
            "--model_citation",
            model_citation,
            "--model_review",
            model_review,
            "--model_agg_plots",
            model_agg_plots,
            "--num_cite_rounds",
            str(num_cite_rounds),
        ]
        if add_dataset_ref:
            cmd.append("--add_dataset_ref")
        if load_code:
            cmd.append("--load_code")
        
        with open(log_file, "w") as log:
            subprocess.Popen(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)
        return

    # Treat as .md workflow: use a small helper that runs ideation then launch
    if path.suffix == ".md" and path.exists():
        log_name = f"pipeline_from_md_{path.stem}_attempt_{attempt_id}"
        log_file = f"/tmp/{log_name}.log"
        
        cmd = [
            py,
            str(ROOT / "ai_scientist" / "dashboard" / "launch_from_md.py"),
            "--workshop-file",
            str(path),
            "--writeup-type",
            writeup_type,
            "--attempt_id",
            str(attempt_id),
            "--model_writeup",
            model_writeup,
            "--model_citation",
            model_citation,
            "--model_review",
            model_review,
            "--model_agg_plots",
            model_agg_plots,
            "--num_cite_rounds",
            str(num_cite_rounds),
        ]
        if add_dataset_ref:
            cmd.append("--add_dataset_ref")
        if load_code:
            cmd.append("--load_code")
        
        with open(log_file, "w") as log:
            subprocess.Popen(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)
        return

    raise FileNotFoundError(f"Idea path not found: {idea_json_path}")


