from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from ai_scientist.dashboard import utils
from ai_scientist.dashboard import view_models


def test_load_idea_document_parses_markdown_and_json(tmp_path: Path) -> None:
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    md_path = ideas_dir / "demo.md"
    md_path.write_text(
        """# Title
Demo Title

# Keywords
ai, science

# TL;DR
Short summary

# Abstract
Longer abstract text.
"""
    )
    json_path = md_path.with_suffix(".json")
    json_path.write_text(
        """
[
  {
    "Name": "demo_idea",
    "Title": "Demo Idea Title",
    "Short Hypothesis": "A compact hypothesis.",
    "Abstract": "An abstract.",
    "Experiments": "- experiment one"
  }
]
"""
    )

    doc = view_models.load_idea_document(md_path)

    assert doc.slug == "demo"
    assert doc.title == "Demo Title"
    assert doc.keywords == ["ai", "science"]
    assert doc.tldr == "Short summary"
    assert doc.abstract.startswith("Longer")
    assert doc.has_proposals
    assert doc.proposals[0].display_title == "Demo Idea Title"
    assert "- experiment one" in doc.proposals[0].experiments


def test_parse_experiment_folder_name_handles_timestamp() -> None:
    started_at, idea_slug, attempt = view_models.parse_experiment_folder_name(
        "2025-01-15_12-30-00_super_idea_attempt_3"
    )
    assert attempt == 3
    assert idea_slug == "super_idea"
    assert started_at == datetime(2025, 1, 15, 12, 30, 0)


def test_load_experiment_snapshot_tracks_recent_activity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    exp_dir = tmp_path / "experiments" / "2025-01-15_12-30-00_super_idea_attempt_1"
    exp_dir.mkdir(parents=True)

    log_root = tmp_path / "tmp"
    log_root.mkdir()
    monkeypatch.setattr(view_models, "LOG_ROOT", log_root)

    log_path = log_root / "pipeline_super_idea_attempt_1.log"
    log_path.write_text("Test log line\n")

    status_payload = {
        "stage_summary": "Stage A running",
        "progress_ratio": 0.5,
        "current_stage": "Stage A",
        "total_nodes": 10,
        "good_nodes": 6,
        "buggy_nodes": 2,
        "stages": [
            {
                "name": "Stage A",
                "total_nodes": 10,
                "good_nodes": 6,
                "buggy_nodes": 2,
                "notes": "Investigating candidates",
            }
        ],
    }
    artifacts_payload = {
        "figures": [tmp_path / "figures" / "plot.png"],
        "experiment_plots": [],
        "pdf": None,
        "tree_html": None,
    }
    artifacts_payload["figures"][0].parent.mkdir(exist_ok=True)
    artifacts_payload["figures"][0].write_text("fake image bytes")

    monkeypatch.setattr(utils, "read_experiment_status", lambda _: status_payload)
    monkeypatch.setattr(utils, "read_experiment_artifacts", lambda _: artifacts_payload)

    snapshot = view_models.load_experiment_snapshot(exp_dir)

    assert snapshot.name == exp_dir.name
    assert snapshot.progress_ratio == 0.5
    assert snapshot.current_stage == "Stage A"
    assert snapshot.is_running  # recent log activity triggers running flag
    assert snapshot.artifact_counts["figures"] == 1
    assert snapshot.log_path == log_path
    assert snapshot.latest_note == "Investigating candidates"
    assert snapshot.last_updated is not None
