from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ai_scientist.dashboard import utils

LOG_ROOT = Path("/tmp")
TIMESTAMP_PATTERN = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})(?:_(?P<time>\d{2}-\d{2}-\d{2}))?"
)


@dataclass
class IdeaProposal:
    name: str
    title: str
    short_hypothesis: str
    abstract: str
    experiments: str
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def display_title(self) -> str:
        return self.title or self.name or "Untitled proposal"

    @property
    def summary(self) -> str:
        if self.short_hypothesis:
            return self.short_hypothesis
        return self.abstract or ""


@dataclass
class IdeaDocument:
    slug: str
    md_path: Path
    json_path: Path
    title: str = ""
    keywords: List[str] = field(default_factory=list)
    tldr: str = ""
    abstract: str = ""
    proposals: List[IdeaProposal] = field(default_factory=list)

    @property
    def exists(self) -> bool:
        return self.md_path.exists()

    @property
    def has_proposals(self) -> bool:
        return bool(self.proposals)

    @property
    def display_name(self) -> str:
        return self.title or self.slug.replace("_", " ").title()


@dataclass
class ExperimentSnapshot:
    name: str
    path: Path
    idea_slug: str
    attempt_id: Optional[int]
    started_at: Optional[datetime]
    status_text: str
    progress_ratio: Optional[float]
    current_stage: Optional[str]
    stage_details: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    artifacts: Dict[str, Any]
    artifact_counts: Dict[str, int]
    log_path: Optional[Path]
    last_updated: Optional[datetime]
    is_running: bool
    latest_note: Optional[str]

    @property
    def progress_percent(self) -> Optional[int]:
        if self.progress_ratio is None:
            return None
        return int(max(0.0, min(1.0, self.progress_ratio)) * 100)

    @property
    def headline(self) -> str:
        if self.current_stage:
            return f"{self.current_stage}: {self.status_text}"
        return self.status_text


def load_all_ideas() -> List[IdeaDocument]:
    idea_docs: List[IdeaDocument] = []
    for md_path in utils.list_ideas():
        idea_docs.append(load_idea_document(md_path))
    return sorted(idea_docs, key=lambda doc: doc.slug)


def load_idea_document(md_path: Path) -> IdeaDocument:
    slug = md_path.stem
    sections = _parse_markdown_sections(md_path) if md_path.exists() else {}
    json_path = md_path.with_suffix(".json")
    proposals = _load_proposals(json_path)
    return IdeaDocument(
        slug=slug,
        md_path=md_path,
        json_path=json_path,
        title=sections.get("title", ""),
        keywords=[kw.strip() for kw in sections.get("keywords", "").split(",") if kw.strip()],
        tldr=sections.get("tl;dr", "") or sections.get("tldr", ""),
        abstract=sections.get("abstract", ""),
        proposals=proposals,
    )


def load_experiment_snapshots() -> List[ExperimentSnapshot]:
    snapshots: List[ExperimentSnapshot] = []
    for exp_dir in utils.list_experiments():
        snapshots.append(load_experiment_snapshot(exp_dir))
    snapshots.sort(
        key=lambda snap: snap.last_updated or snap.started_at or datetime.fromtimestamp(0),
        reverse=True,
    )
    return snapshots


def load_experiment_snapshot(exp_dir: Path) -> ExperimentSnapshot:
    status = utils.read_experiment_status(exp_dir)
    artifacts = utils.read_experiment_artifacts(exp_dir)
    artifact_counts = _summarize_artifacts(artifacts)

    started_at, idea_slug, attempt_id = parse_experiment_folder_name(exp_dir.name)
    log_path = infer_log_path(exp_dir.name, idea_slug, attempt_id)

    latest_note = None
    stages = status.get("stages") or []
    if stages:
        notes = stages[-1].get("notes")
        if isinstance(notes, str):
            latest_note = notes

    last_updated = _compute_last_updated(exp_dir, log_path, artifacts)

    metrics = {
        "total_nodes": status.get("total_nodes", 0),
        "good_nodes": status.get("good_nodes", 0),
        "buggy_nodes": status.get("buggy_nodes", 0),
    }

    log_is_recent = False
    if log_path and log_path.exists():
        log_is_recent = (time.time() - log_path.stat().st_mtime) < 300

    is_running = log_is_recent or (status.get("progress_ratio") not in (None, 1.0))

    return ExperimentSnapshot(
        name=exp_dir.name,
        path=exp_dir,
        idea_slug=idea_slug or "",
        attempt_id=attempt_id,
        started_at=started_at,
        status_text=status.get("stage_summary", "Pending..."),
        progress_ratio=status.get("progress_ratio"),
        current_stage=status.get("current_stage"),
        stage_details=stages,
        metrics=metrics,
        artifacts=artifacts,
        artifact_counts=artifact_counts,
        log_path=log_path,
        last_updated=last_updated,
        is_running=is_running,
        latest_note=latest_note,
    )


def parse_experiment_folder_name(name: str) -> Tuple[Optional[datetime], Optional[str], Optional[int]]:
    attempt_id: Optional[int] = None
    base = name
    if "_attempt_" in name:
        try:
            base, attempt_str = name.rsplit("_attempt_", 1)
            attempt_id = int(attempt_str)
        except ValueError:
            attempt_id = None

    started_at: Optional[datetime] = None
    idea_slug: Optional[str] = None

    match = TIMESTAMP_PATTERN.match(base)
    if match:
        date_part = match.group("date")
        time_part = match.group("time")
        ts_string = date_part
        fmt = "%Y-%m-%d"
        if time_part:
            ts_string = f"{date_part}_{time_part}"
            fmt = "%Y-%m-%d_%H-%M-%S"
        try:
            started_at = datetime.strptime(ts_string, fmt)
        except ValueError:
            started_at = None
        remaining = base[len(ts_string):].lstrip("_")
        idea_slug = remaining or None
    else:
        parts = base.split("_", 1)
        if len(parts) == 2:
            try:
                started_at = datetime.strptime(parts[0], "%Y-%m-%d")
                idea_slug = parts[1]
            except ValueError:
                idea_slug = base
        else:
            idea_slug = base

    return started_at, idea_slug, attempt_id


def infer_log_path(exp_name: str, idea_slug: Optional[str], attempt_id: Optional[int]) -> Optional[Path]:
    if attempt_id is None or not idea_slug:
        return None
    candidates = [
        LOG_ROOT / f"pipeline_{idea_slug}_attempt_{attempt_id}.log",
        LOG_ROOT / f"pipeline_from_md_{idea_slug}_attempt_{attempt_id}.log",
        LOG_ROOT / f"{exp_name}.log",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0] if candidates else None


def read_log_tail(log_path: Path, max_lines: int = 200) -> str:
    if not log_path.exists():
        return ""
    text = log_path.read_text(errors="ignore")
    lines = text.splitlines()[-max_lines:]
    return "\n".join(lines)


def _parse_markdown_sections(md_path: Path) -> Dict[str, str]:
    sections: Dict[str, List[str]] = {}
    current = None
    for line in md_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            header = stripped.lstrip("#").strip().lower()
            current = header
            sections.setdefault(current, [])
            continue
        if current is None:
            continue
        sections[current].append(stripped)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _load_proposals(json_path: Path) -> List[IdeaProposal]:
    if not json_path.exists():
        return []
    try:
        payload = json.loads(json_path.read_text())
    except json.JSONDecodeError:
        return []
    proposals: List[IdeaProposal] = []
    if isinstance(payload, dict):
        payload = payload.get("ideas") or payload.get("results") or [payload]
    if not isinstance(payload, Iterable):
        return proposals
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        proposals.append(
            IdeaProposal(
                name=str(entry.get("Name") or entry.get("name") or ""),
                title=str(entry.get("Title") or entry.get("title") or ""),
                short_hypothesis=str(
                    entry.get("Short Hypothesis")
                    or entry.get("short_hypothesis")
                    or entry.get("TLDR")
                    or entry.get("TL;DR")
                    or entry.get("Summary")
                    or entry.get("summary")
                    or ""
                ),
                abstract=str(entry.get("Abstract") or entry.get("abstract") or ""),
                experiments=str(entry.get("Experiments") or entry.get("experiments") or ""),
                raw=entry,
            )
        )
    return proposals


def _summarize_artifacts(artifacts: Dict[str, Any]) -> Dict[str, int]:
    return {
        "figures": len(artifacts.get("figures") or []),
        "experiment_plots": len(artifacts.get("experiment_plots") or []),
        "pdf": 1 if artifacts.get("pdf") else 0,
        "tree_html": 1 if artifacts.get("tree_html") else 0,
    }


def _compute_last_updated(
    exp_dir: Path, log_path: Optional[Path], artifacts: Dict[str, Any]
) -> Optional[datetime]:
    timestamps: List[float] = []
    try:
        timestamps.append(exp_dir.stat().st_mtime)
    except FileNotFoundError:
        pass

    if log_path and log_path.exists():
        timestamps.append(log_path.stat().st_mtime)

    for key in ("figures", "experiment_plots"):
        for artifact_path in artifacts.get(key) or []:
            try:
                timestamps.append(artifact_path.stat().st_mtime)
            except FileNotFoundError:
                continue

    for key in ("pdf", "tree_html"):
        artifact_path = artifacts.get(key)
        if isinstance(artifact_path, Path) and artifact_path.exists():
            timestamps.append(artifact_path.stat().st_mtime)

    if not timestamps:
        return None
    return datetime.fromtimestamp(max(timestamps))

