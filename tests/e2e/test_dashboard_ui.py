from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

import pytest
import requests
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
STREAMLIT_APP = REPO_ROOT / "ai_scientist" / "dashboard" / "app.py"
STREAMLIT_PORT = 8765


def _ensure_seed_data() -> Path | None:
    ideas_dir = REPO_ROOT / "ai_scientist" / "ideas"
    ideas_dir.mkdir(exist_ok=True)
    existing = list(ideas_dir.glob("*.md"))
    if existing:
        return None
    seed_md = ideas_dir / "ui_smoke_test.md"
    if not seed_md.exists():
        seed_md.write_text(
            """# Title
UI Smoke Test Idea

# Keywords
ui,smoke

# TL;DR
This is a generated idea to support UI smoke tests.

# Abstract
The purpose of this document is to ensure the dashboard renders content during automation.
"""
        )
    return seed_md


def _wait_for_streamlit(url: str, timeout: int = 60) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code < 500:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise TimeoutError(f"Streamlit app did not start at {url} within {timeout} seconds.")


@pytest.fixture(scope="session")
def streamlit_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    created_seed = _ensure_seed_data()

    env = os.environ.copy()
    env.update(
        {
            "STREAMLIT_SERVER_PORT": str(STREAMLIT_PORT),
            "STREAMLIT_SERVER_HEADLESS": "true",
            "STREAMLIT_SERVER_ENABLE_CORS": "false",
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        }
    )

    log_dir = tmp_path_factory.mktemp("streamlit_logs")
    stdout_path = log_dir / "stdout.log"
    stderr_path = log_dir / "stderr.log"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(STREAMLIT_APP),
                f"--server.port={STREAMLIT_PORT}",
                "--server.headless=true",
                "--server.fileWatcherType=none",
            ],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=stdout,
            stderr=stderr,
        )
    try:
        _wait_for_streamlit(f"http://localhost:{STREAMLIT_PORT}")
        yield f"http://localhost:{STREAMLIT_PORT}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        if created_seed and created_seed.exists():
            created_seed.unlink()
            seed_json = created_seed.with_suffix(".json")
            if seed_json.exists():
                seed_json.unlink()


def test_dashboard_overview_renders(streamlit_server: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(streamlit_server, wait_until="networkidle")
        page.wait_for_selector("text=AI Scientist Orchestrator")
        page.wait_for_selector("text=Idea Studio")
        page.wait_for_selector("text=Experiments Overview")
        browser.close()
