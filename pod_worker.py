import argparse
import os
import sys
import time
import json
import hashlib
import traceback
import requests
import socket
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from functools import partial
from pymongo import MongoClient, ReturnDocument
from ulid import ULID

# Load .env at module import time to ensure env vars are available
# This is critical for worker restarts after git auto-pull
if os.path.exists('.env'):
    from dotenv import load_dotenv
    load_dotenv(override=True)

from event_emitter import CloudEventEmitter

CONTROL_PLANE_URL = os.environ.get("CONTROL_PLANE_URL", "https://ai-scientist-v2-production.up.railway.app")
MONGODB_URL = os.environ.get("MONGODB_URL", "")
POD_ID = os.environ.get("RUNPOD_POD_ID", socket.gethostname())

# Git auto-update configuration
GIT_AUTO_PULL_ENABLED = os.environ.get("GIT_AUTO_PULL_ENABLED", "true").lower() == "true"
GIT_AUTO_PULL_INTERVAL = int(os.environ.get("GIT_AUTO_PULL_INTERVAL", "60"))  # seconds
GIT_AUTO_PULL_BRANCH = os.environ.get("GIT_AUTO_PULL_BRANCH", "main")

CURRENT_RUN_ID: Optional[str] = None
CURRENT_STAGE: Optional[str] = None

event_emitter = CloudEventEmitter(CONTROL_PLANE_URL, POD_ID)


class RunCanceledException(Exception):
    """Raised when a run is canceled by the user during execution."""
    pass


def ensure_run_not_canceled(db_obj, run_id: str):
    """Raise RunCanceledException if the run has been marked as canceled."""
    run_doc = db_obj['runs'].find_one({"_id": run_id}, {"status": 1})
    if run_doc and run_doc.get("status") == "CANCELED":
        raise RunCanceledException(f"Run {run_id} marked as canceled")


def _handle_experiment_event(run_id, emit_event_func, emitter_obj, db_obj, event_type: str, data: dict):
    """
    Module-level event handler for experiments that can be pickled for multiprocessing.
    
    Args:
        run_id: The run identifier
        emit_event_func: Function to emit events
        emitter_obj: The emitter object for flushing
        db_obj: MongoDB database object
        event_type: Type of event
        data: Event data dictionary
    """
    data["run_id"] = run_id
    emit_event_func(event_type, data)
    emitter_obj.flush()
    
    # Update MongoDB currentStage when internal BFTS stages progress
    if event_type == "ai.run.stage_progress":
        try:
            internal_stage = data.get("stage", "")
            progress = data.get("progress", 0.0)
            # Clamp progress to [0, 1] to prevent validation errors
            progress = max(0.0, min(progress, 1.0))
            iteration = data.get("iteration", 0)
            max_iterations = data.get("max_iterations", 1)
            good_nodes = data.get("good_nodes", 0)
            buggy_nodes = data.get("buggy_nodes", 0)
            total_nodes = data.get("total_nodes", 0)
            
            # Map internal BFTS stage names to user-friendly names
            substage_display_names = {
                "1_initial": "Initial Implementation",
                "2_baseline": "Baseline Tuning",
                "3_creative": "Creative Research",
                "4_ablation": "Ablation Studies",
                # Legacy formats just in case
                "stage_1": "Initial Implementation",
                "stage_2": "Baseline Tuning",
                "stage_3": "Creative Research",
                "stage_4": "Ablation Studies"
            }
            
            substage_name = substage_display_names.get(internal_stage, internal_stage)
            
            print(f"🔄 Updating UI: Stage_1 → {substage_name} - {progress*100:.1f}% ({good_nodes}/{total_nodes} nodes)")
            
            # Keep Stage_1 as main stage
            stage_data = {
                "name": "Stage_1",
                "progress": progress,
                "iteration": iteration,
                "maxIterations": max_iterations,
                "goodNodes": good_nodes,
                "buggyNodes": buggy_nodes,
                "totalNodes": total_nodes,
                "bestMetric": data.get("best_metric")
            }
            
            db_obj['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage": stage_data}}
            )

            # Allow long-running Stage 1 loops to stop promptly on user-cancel.
            ensure_run_not_canceled(db_obj, run_id)
        except Exception as e:
            print(f"Failed to update currentStage in MongoDB: {e}")
            traceback.print_exc()


def find_best_pdf_for_review(pdf_files):
    """
    Intelligently select the best PDF for review from a list of PDFs.
    Prioritizes: final PDFs > highest numbered reflections > any reflection > any PDF
    
    Args:
        pdf_files: List of PDF filenames (just filenames, not full paths)
    
    Returns:
        str: The filename of the best PDF to review
    """
    if not pdf_files:
        return None
    
    # Separate reflection PDFs from others
    reflection_pdfs = [f for f in pdf_files if "reflection" in f.lower()]
    
    if reflection_pdfs:
        # First check if there's a final version
        final_pdfs = [f for f in reflection_pdfs if "final" in f.lower()]
        if final_pdfs:
            return final_pdfs[0]
        
        # Try to find numbered reflections and pick the highest
        reflection_nums = []
        for f in reflection_pdfs:
            match = re.search(r"reflection[_.]?(\d+)", f, re.IGNORECASE)
            if match:
                reflection_nums.append((int(match.group(1)), f))
        
        if reflection_nums:
            # Get the file with the highest reflection number
            highest_reflection = max(reflection_nums, key=lambda x: x[0])
            return highest_reflection[1]
        else:
            # Fall back to the first reflection PDF if no numbers found
            return reflection_pdfs[0]
    
    # No reflection PDFs, use any PDF (prefer ones without "draft" in name)
    non_draft_pdfs = [f for f in pdf_files if "draft" not in f.lower()]
    if non_draft_pdfs:
        return non_draft_pdfs[0]
    
    return pdf_files[0]


def git_pull():
    """
    Pull latest changes from git repository.
    Returns True if successful, False otherwise.
    """
    if not GIT_AUTO_PULL_ENABLED:
        return True
    
    try:
        # Get current directory (should be the repo root)
        repo_dir = Path(__file__).parent.absolute()
        
        print(f"📥 Pulling latest changes from git ({GIT_AUTO_PULL_BRANCH})...", end=" ", flush=True)
        
        # Fetch latest changes
        result = subprocess.run(
            ["git", "fetch", "origin", GIT_AUTO_PULL_BRANCH],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"⚠️  Git fetch failed: {result.stderr.strip()}")
            return False
        
        # Check if there are changes to pull
        result = subprocess.run(
            ["git", "rev-list", "--count", f"HEAD..origin/{GIT_AUTO_PULL_BRANCH}"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print(f"⚠️  Git rev-list failed: {result.stderr.strip()}")
            return False
        
        commits_behind = int(result.stdout.strip())
        
        if commits_behind == 0:
            print("✓ Already up to date")
            return True
        
        # Pull changes
        result = subprocess.run(
            ["git", "pull", "origin", GIT_AUTO_PULL_BRANCH],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"⚠️  Git pull failed: {result.stderr.strip()}")
            return False
        
        print(f"✓ Pulled {commits_behind} new commit(s)")
        
        # Check if this file (pod_worker.py) was updated
        result = subprocess.run(
            ["git", "diff", "--name-only", f"HEAD~{commits_behind}", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if "pod_worker.py" in result.stdout:
            print("🔄 pod_worker.py was updated - restarting worker with new version...")
            print("   (This is safe since we're between experiments or writeup retries)")
            
            # Get the full path to this script
            script_path = Path(__file__).absolute()
            
            # Use execv to replace the current process with a fresh Python interpreter
            # running the new code. This is NOT a subprocess - it's process replacement:
            # - Same PID (process ID doesn't change)
            # - Environment variables are automatically inherited
            # - No parent-child relationship
            # - Old process memory is completely replaced with new code
            # - Atomic operation - no race conditions
            os.execv(sys.executable, [sys.executable, str(script_path)])
            # Note: code after execv never runs - process is replaced
        
        return True
        
    except subprocess.TimeoutExpired:
        print("⚠️  Git operation timed out")
        return False
    except Exception as e:
        print(f"⚠️  Git pull error: {e}")
        return False


class EventEmitter:
    def __init__(self, control_plane_url: str, pod_id: str):
        self.control_plane_url = control_plane_url
        self.pod_id = pod_id
        self.batch = []
        self.batch_size = 50
    
    def emit(self, event_type: str, data: Dict[str, Any], run_id: str):
        global EVENT_SEQ
        EVENT_SEQ += 1
        
        event = {
            "specversion": "1.0",
            "id": str(ULID()),
            "source": f"runpod://pod/{self.pod_id}",
            "type": event_type,
            "subject": f"run/{run_id}",
            "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "datacontenttype": "application/json",
            "data": data,
            "extensions": {
                "seq": EVENT_SEQ
            }
        }
        
        self.batch.append(event)
        
        if len(self.batch) >= self.batch_size:
            self.flush()
    
    def flush(self):
        if not self.batch:
            return
        
        if len(self.batch) == 1:
            try:
                response = requests.post(
                    f"{self.control_plane_url}/api/ingest/event",
                    json=self.batch[0],
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                response.raise_for_status()
                print(f"✓ Sent 1 event")
            except requests.exceptions.HTTPError as e:
                print(f"✗ Failed to send event: {e}", file=sys.stderr)
                try:
                    error_detail = e.response.json() if e.response else {}
                    if error_detail:
                        print(f"   Error details: {json.dumps(error_detail, indent=2)}", file=sys.stderr)
                        print(f"   Event type: {self.batch[0].get('type')}", file=sys.stderr)
                        print(f"   Event data keys: {list(self.batch[0].get('data', {}).keys())}", file=sys.stderr)
                except:
                    pass
            except Exception as e:
                print(f"✗ Failed to send event: {e}", file=sys.stderr)
        else:
            ndjson = "\n".join(json.dumps(event) for event in self.batch)
            
            try:
                response = requests.post(
                    f"{self.control_plane_url}/api/ingest/events",
                    data=ndjson,
                    headers={"Content-Type": "application/x-ndjson"},
                    timeout=30
                )
                response.raise_for_status()
                print(f"✓ Sent {len(self.batch)} events")
            except requests.exceptions.HTTPError as e:
                print(f"✗ Failed to send events: {e}", file=sys.stderr)
                try:
                    error_detail = e.response.json() if e.response else {}
                    if error_detail:
                        print(f"   Error details: {json.dumps(error_detail, indent=2)}", file=sys.stderr)
                        event_types = [event.get('type') for event in self.batch]
                        print(f"   Event types in batch: {event_types}", file=sys.stderr)
                except:
                    pass
            except Exception as e:
                print(f"✗ Failed to send events: {e}", file=sys.stderr)
            finally:
                self.batch = []


emitter = EventEmitter(CONTROL_PLANE_URL, POD_ID)


def emit_event(event_type: str, data: Dict[str, Any]):
    if not CURRENT_RUN_ID:
        print(f"⚠ Cannot emit {event_type}: no active run", file=sys.stderr)
        return
    emitter.emit(event_type, data, CURRENT_RUN_ID)


def global_exception_handler(exc_type, exc_value, exc_traceback):
    error_info = {
        "type": exc_type.__name__,
        "message": str(exc_value),
        "traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    }
    
    print(f"\n❌ UNHANDLED EXCEPTION: {error_info['type']}: {error_info['message']}", file=sys.stderr)
    
    try:
        emit_event("ai.run.failed", {
            "run_id": CURRENT_RUN_ID,
            "stage": CURRENT_STAGE or "unknown",
            "code": error_info["type"],
            "message": error_info["message"],
            "traceback": error_info["traceback"],
            "retryable": is_retryable(exc_type)
        })
        emitter.flush()
    except:
        print(f"CRITICAL: Failed to emit error event", file=sys.stderr)
    
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


sys.excepthook = global_exception_handler


# Global shutdown flag
SHUTDOWN_REQUESTED = False

def signal_handler(signum, frame):
    """Handle Ctrl+C and SIGTERM gracefully"""
    global SHUTDOWN_REQUESTED
    sig_name = "SIGINT" if signum == 2 else "SIGTERM" if signum == 15 else f"Signal {signum}"
    print(f"\n🛑 Received {sig_name} - shutting down gracefully...")
    SHUTDOWN_REQUESTED = True
    
    try:
        if CURRENT_RUN_ID:
            from pymongo import MongoClient
            client = MongoClient(MONGODB_URL)
            db = client['ai-scientist']
            
            # Check current status - don't cancel if already completed/failed
            run = db['runs'].find_one({'_id': CURRENT_RUN_ID})
            if run and run.get('status') in ['COMPLETED', 'FAILED']:
                print(f"Run {CURRENT_RUN_ID} already {run.get('status')}, not canceling")
            else:
                print(f"Marking run {CURRENT_RUN_ID} as CANCELED...")
                db['runs'].update_one(
                    {'_id': CURRENT_RUN_ID},
                    {'$set': {
                        'status': 'CANCELED',
                        'canceledAt': datetime.utcnow()
                    }}
                )
                
                emit_event("ai.run.canceled", {
                    "run_id": CURRENT_RUN_ID,
                    "reason": f"Worker received {sig_name}",
                    "stage": CURRENT_STAGE or "unknown"
                })
                emitter.flush()
                print(f"✓ Run marked as CANCELED")
    except Exception as e:
        print(f"Failed to mark run as canceled: {e}")
    
    sys.exit(0)

import signal
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class StageContext:
    def __init__(self, stage_name: str, run_id: str):
        self.stage = stage_name
        self.run_id = run_id
        self.start_time = None
    
    def __enter__(self):
        global CURRENT_STAGE, CURRENT_RUN_ID
        CURRENT_STAGE = self.stage
        CURRENT_RUN_ID = self.run_id
        self.start_time = time.time()
        
        event_emitter.stage_started(
            self.run_id,
            self.stage,
            get_stage_description(self.stage)
        )
        return self
    
    def __exit__(self, exc_type, exc_value, exc_traceback):
        from pymongo import MongoClient
        duration_s = time.time() - self.start_time if self.start_time else 0
        
        if exc_type is not None:
            # Don't emit failure event here - let the outer exception handler do it
            # This prevents premature "failed" status when exceptions are caught and handled
            # The top-level try-catch in run_experiment_pipeline will emit the failure event
            # if the experiment truly fails
            print(f"⚠️ Exception in stage {self.stage}: {exc_type.__name__}: {exc_value}", file=sys.stderr)
            return False  # Re-raise the exception
        
        # Save stage duration
        try:
            client = MongoClient(MONGODB_URL)
            db = client['ai-scientist']
            db['runs'].update_one(
                {'_id': self.run_id},
                {'$set': {f'stageTiming.{self.stage}.duration_s': int(duration_s)}}
            )
        except:
            pass
        
        # Emit stage completed event
        # Try both CloudEventEmitter and batched emitter for maximum reliability
        success = event_emitter.stage_completed(
            self.run_id,
            self.stage,
            int(duration_s)
        )
        
        # Also send via batched emitter as backup
        emit_event("ai.run.stage_completed", {
            "run_id": self.run_id,
            "stage": self.stage,
            "duration_s": int(duration_s)
        })
        emitter.flush()
        
        # Update stage in MongoDB directly to ensure it's marked as completed
        try:
            client = MongoClient(MONGODB_URL)
            db = client['ai-scientist']
            db['stages'].update_one(
                {'runId': self.run_id, 'name': self.stage},
                {'$set': {
                    'status': 'COMPLETED',
                    'completedAt': datetime.utcnow(),
                    'progress': 1.0
                }}
            )
            print(f"✓ Stage {self.stage} completed in {int(duration_s)}s")
        except Exception as e:
            print(f"⚠️ Failed to update stage status in MongoDB: {e}")
            if not success:
                print(f"⚠️ Also failed to emit stage_completed event")
        
        return False


def is_retryable(exc_type) -> bool:
    retryable_errors = [
        ConnectionError,
        TimeoutError,
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
    ]
    return any(isinstance(exc_type, e) for e in retryable_errors)


def get_stage_description(stage: str) -> str:
    descriptions = {
        "Stage_1": "Preliminary Investigation",
        "Stage_2": "Baseline Tuning",
        "Stage_3": "Research Agenda Execution",
        "Stage_4": "Ablation Studies"
    }
    return descriptions.get(stage, stage)


def fetch_next_experiment(mongo_client, pod_id: str) -> Optional[Dict[str, Any]]:
    db = mongo_client['ai-scientist']
    runs_collection = db["runs"]
    
    gpu_info = get_gpu_info()
    
    run = runs_collection.find_one_and_update(
        {
            "status": "QUEUED",
            "claimedBy": None
        },
        {
            "$set": {
                "status": "SCHEDULED",
                "claimedBy": pod_id,
                "claimedAt": datetime.utcnow(),
                "pod": {
                    "id": pod_id,
                    "instanceType": gpu_info.get("gpu_name"),
                    "region": gpu_info.get("region")
                }
            }
        },
        sort=[("createdAt", 1)],
        return_document=ReturnDocument.AFTER
    )
    
    return run


def fetch_next_ideation(mongo_client, pod_id: str) -> Optional[Dict[str, Any]]:
    db = mongo_client["ai-scientist"]
    ideation_collection = db["ideation_requests"]
    
    try:
        queued_count = ideation_collection.count_documents({"status": "QUEUED"})
        running_count = ideation_collection.count_documents({"status": "RUNNING"})
        print(
            f"[ideation-debug] DB=ai-scientist queued={queued_count} running={running_count} pod={pod_id}"
        )
    except Exception as e:
        print(f"[ideation-debug] Failed to count ideation requests: {e}")
    
    request = ideation_collection.find_one_and_update(
        {
            "status": "QUEUED",
            "$or": [
                {"claimedBy": None},
                {"claimedBy": {"$exists": False}}
            ]
        },
        {
            "$set": {
                "status": "RUNNING",
                "claimedBy": pod_id,
                "claimedAt": datetime.utcnow(),
                "startedAt": datetime.utcnow()
            }
        },
        sort=[("createdAt", 1)],
        return_document=ReturnDocument.AFTER
    )
    
    if request:
        print(
            "[ideation-debug] Claimed ideation request "
            f"id={request.get('_id')} hypothesisId={request.get('hypothesisId')} "
            f"reflections={request.get('reflections')} createdAt={request.get('createdAt')}"
        )
    else:
        print("[ideation-debug] No ideation request claimed on this poll")
    
    return request


def _slugify_name(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or fallback


def _coerce_string_list(value) -> List[str]:
    if isinstance(value, list):
        normalized = []
        for item in value:
            if isinstance(item, str):
                candidate = item.strip()
            else:
                candidate = str(item).strip()
            if candidate:
                normalized.append(candidate)
        return normalized
    if isinstance(value, str):
        lines = []
        for line in value.replace("\r", "").split("\n"):
            candidate = line.strip(" -*\t")
            if candidate:
                lines.append(candidate)
        return lines
    return []


def _normalize_idea_payload(raw: Dict[str, Any], defaults: Dict[str, str]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    idea = {
        "Name": raw.get("Name") or raw.get("name") or defaults["name"],
        "Title": raw.get("Title") or raw.get("title") or defaults["title"],
        "Short Hypothesis": raw.get("Short Hypothesis")
        or raw.get("Hypothesis")
        or defaults["short"],
        "Abstract": raw.get("Abstract") or defaults["abstract"],
        "Experiments": _coerce_string_list(raw.get("Experiments")),
        "Risk Factors and Limitations": _coerce_string_list(
            raw.get("Risk Factors and Limitations")
        )
    }
    related = raw.get("Related Work") or raw.get("related_work")
    if isinstance(related, str) and related.strip():
        idea["Related Work"] = related.strip()
    return idea


def fetch_writeup_retry(mongo_client, pod_id: str) -> Optional[Dict[str, Any]]:
    db = mongo_client['ai-scientist']
    runs_collection = db["runs"]
    
    run = runs_collection.find_one_and_update(
        {
            "pendingWriteupRetry": True,
            "$or": [
                {"writeupRetryClaimedBy": None},
                {"writeupRetryClaimedBy": {"$exists": False}}
            ]
        },
        {
            "$set": {
                "writeupRetryClaimedBy": pod_id,
                "writeupRetryClaimedAt": datetime.utcnow()
            }
        },
        sort=[("writeupRetryRequestedAt", 1)],
        return_document=ReturnDocument.AFTER
    )
    
    return run


def get_gpu_info() -> Dict[str, Any]:
    try:
        import torch
        if torch.cuda.is_available():
            return {
                "gpu_name": torch.cuda.get_device_name(0),
                "gpu_count": torch.cuda.device_count(),
                "region": os.environ.get("RUNPOD_DATACENTER", "unknown")
            }
    except:
        pass
    return {"gpu_name": "unknown", "gpu_count": 0, "region": "unknown"}


def upload_artifact(run_id: str, file_path: str, kind: str) -> bool:
    try:
        filename = os.path.basename(file_path)
        content_type = get_content_type(filename)
        
        print(f"📤 Uploading artifact: {filename} ({kind})")
        
        resp = requests.post(
            f"{CONTROL_PLANE_URL}/api/runs/{run_id}/artifacts/presign",
            json={"action": "put", "filename": filename, "content_type": content_type},
            timeout=30
        )
        resp.raise_for_status()
        presigned_url = resp.json()["url"]
        
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        
        print(f"   Uploading {len(file_bytes)} bytes to MinIO...")
        resp = requests.put(presigned_url, data=file_bytes, timeout=300)
        resp.raise_for_status()
        
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        
        print(f"   Registering artifact in database...")
        event_emitter.artifact_registered(
            run_id,
            f"runs/{run_id}/{filename}",
            len(file_bytes),
            sha256,
            content_type,
            kind
        )
        
        print(f"✓ Artifact uploaded successfully: {filename}")
        return True
    except Exception as e:
        # Artifact failed event
        print(f"❌ Artifact upload failed: {e}")
        traceback.print_exc()
        return False


def get_content_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if filename.endswith('.tar.gz'):
        return "application/gzip"
    types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".json": "application/json",
        ".txt": "text/plain",
        ".gz": "application/gzip",
        ".tar": "application/x-tar",
    }
    return types.get(ext, "application/octet-stream")


def copy_best_solutions_to_root(idea_dir: str):
    """
    Copy the best solution code from each stage to the experiment root directory
    for easy access and reproducibility.
    """
    try:
        from pathlib import Path
        
        idea_path = Path(idea_dir)
        logs_dir = idea_path / "logs" / "0-run"
        
        if not logs_dir.exists():
            print("⚠️ No logs directory found, skipping best solution copy")
            return
        
        stage_info = []
        best_solutions_copied = 0
        
        # Find all stage directories
        stage_dirs = sorted([d for d in logs_dir.iterdir() if d.is_dir() and d.name.startswith("stage_")])
        
        for stage_dir in stage_dirs:
            # Look for best_solution files
            best_solution_files = list(stage_dir.glob("best_solution_*.py"))
            best_node_id_file = stage_dir / "best_node_id.txt"
            
            if best_solution_files:
                # Get stage name and number
                stage_name = stage_dir.name
                
                # Read node ID if available
                node_id = "unknown"
                if best_node_id_file.exists():
                    with open(best_node_id_file, 'r') as f:
                        node_id = f.read().strip()
                
                # Copy the best solution file
                source_file = best_solution_files[0]
                
                # Create a clean filename based on stage
                # Extract stage number (e.g., stage_3_creative_research_1_first_attempt -> 3)
                stage_num = stage_name.split('_')[1]
                dest_filename = f"best_code_stage_{stage_num}.py"
                dest_path = idea_path / dest_filename
                
                # Copy the file
                import shutil
                shutil.copy2(source_file, dest_path)
                print(f"✓ Copied {dest_filename} (node: {node_id[:8]}...)")
                
                best_solutions_copied += 1
                
                # Store info for README
                stage_info.append({
                    "stage_num": stage_num,
                    "stage_name": stage_name,
                    "filename": dest_filename,
                    "node_id": node_id,
                    "original_path": str(source_file.relative_to(idea_path))
                })
        
        # Create a README explaining the best solutions
        if stage_info:
            readme_path = idea_path / "BEST_SOLUTIONS_README.md"
            with open(readme_path, 'w') as f:
                f.write("# Best Solution Code for Reproducibility\n\n")
                f.write("This directory contains the best performing code from each experimental stage.\n")
                f.write("Use these files to reproduce the results reported in the paper.\n\n")
                
                f.write("## Files\n\n")
                
                stage_descriptions = {
                    "1": "Initial Implementation - First working version of the idea",
                    "2": "Baseline Tuning - Hyperparameter-tuned baseline",
                    "3": "Creative Research - **Main results used in paper**",
                    "4": "Ablation Studies - Variations for comparison"
                }
                
                for info in sorted(stage_info, key=lambda x: int(x["stage_num"])):
                    desc = stage_descriptions.get(info["stage_num"], "Experimental stage")
                    f.write(f"### `{info['filename']}`\n\n")
                    f.write(f"- **Stage**: {desc}\n")
                    f.write(f"- **Node ID**: `{info['node_id']}`\n")
                    f.write(f"- **Original location**: `{info['original_path']}`\n")
                    f.write(f"- **Stage directory**: `{info['stage_name']}`\n\n")
                
                f.write("## How to Use\n\n")
                f.write("For reproducing the main paper results, use **`best_code_stage_3.py`** ")
                f.write("(Creative Research stage).\n\n")
                f.write("```bash\n")
                f.write("# Run the best code\n")
                f.write("python best_code_stage_3.py\n")
                f.write("```\n\n")
                
                f.write("## Selection Process\n\n")
                f.write("The best code for each stage was selected using:\n")
                f.write("- Performance metrics (validation loss, accuracy, etc.)\n")
                f.write("- Training dynamics\n")
                f.write("- Plot quality and experimental evidence\n")
                f.write("- LLM-based evaluation (GPT-5-mini) considering all factors\n\n")
                
                f.write("See `logs/0-run/<stage_name>/journal.json` for the complete ")
                f.write("experimental history and selection reasoning.\n")
            
            print(f"✓ Created BEST_SOLUTIONS_README.md")
        
        print(f"✓ Copied {best_solutions_copied} best solution file(s) to experiment root")
        
    except Exception as e:
        print(f"⚠️ Error copying best solutions: {e}")
        traceback.print_exc()


def run_ideation_pipeline(request: Dict[str, Any], mongo_client) -> None:
    request_id = request["_id"]
    hypothesis_id = request["hypothesisId"]
    reflections = request.get("reflections", 3)
    print(f"\n{'='*60}")
    print(f"🧠 Starting ideation: {request_id}")
    print(f"{'='*60}\n")
    print(
        f"[ideation-debug] Starting pipeline request_id={request_id} "
        f"hypothesis_id={hypothesis_id} reflections={reflections} "
        f"claimedBy={request.get('claimedBy')} claimedAt={request.get('claimedAt')}"
    )
    
    db = mongo_client["ai-scientist"]
    hypotheses_collection = db["hypotheses"]
    ideation_collection = db["ideation_requests"]
    
    hypothesis = hypotheses_collection.find_one({"_id": hypothesis_id})
    if not hypothesis:
        error_msg = f"Hypothesis {hypothesis_id} not found for ideation"
        print(f"❌ {error_msg}")
        print("[ideation-debug] Hypothesis lookup failed during ideation start")
        ideation_collection.update_one(
            {"_id": request_id},
            {
                "$set": {
                    "status": "FAILED",
                    "failedAt": datetime.utcnow(),
                    "error": error_msg,
                    "updatedAt": datetime.utcnow()
                }
            }
        )
        return
    
    started_at = datetime.utcnow()
    hypotheses_collection.update_one(
        {"_id": hypothesis_id},
        {
            "$set": {
                "ideation.status": "RUNNING",
                "ideation.startedAt": started_at
            }
        }
    )
    ideation_collection.update_one(
        {"_id": request_id},
        {
            "$set": {
                "status": "RUNNING",
                "startedAt": started_at,
                "updatedAt": started_at
            }
        }
    )
    
    title = hypothesis.get("title", "Research Direction")
    idea_text = hypothesis.get("idea", "")
    additional_context = hypothesis.get("additionalContext", "")
    defaults = {
        "name": _slugify_name(title, f"idea_{request_id[:8]}"),
        "title": title,
        "short": idea_text[:200] if idea_text else title,
        "abstract": idea_text or title
    }
    
    workspace_root = Path(__file__).parent
    runtime_dir = workspace_root / "ai_scientist" / "ideas" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    
    # Build workshop content, including additional context if provided
    workshop_content = f"# {title}\n\n## Research Prompt\n{idea_text}\n\n"
    if additional_context:
        workshop_content += f"## Additional Context (User Instructions)\n{additional_context}\n\n"
    workshop_content += (
        "## Guidance\n"
        "Generate a compelling research proposal expanding on the hypothesis above. "
        "Use the ideation pipeline tools, perform literature search, and return the final idea JSON.\n"
    )
    
    workshop_path = runtime_dir / f"{request_id}.md"
    workshop_path.write_text(workshop_content, encoding="utf-8")
    print(f"[ideation-debug] Workshop file written to {workshop_path}")
    if additional_context:
        print(f"[ideation-debug] Additional context included: {additional_context[:100]}...")
    
    max_generations = request.get("maxNumGenerations", 1)
    cmd = [
        sys.executable or "python3",
        "ai_scientist/perform_ideation_temp_free.py",
        "--model",
        "gpt-5.1",
        "--workshop-file",
        str(workshop_path),
        "--num-reflections",
        str(reflections),
        "--max-num-generations",
        str(max_generations)
    ]
    
    print(f"🛠️  Running ideation command: {' '.join(cmd)}")
    print(f"[ideation-debug] Running ideation subprocess cwd={workspace_root} timeout=3600s")
    print("[ideation-debug] === STREAMING OUTPUT (real-time) ===\n")
    
    try:
        # Use Popen to stream output in real-time
        process = subprocess.Popen(
            cmd,
            cwd=str(workspace_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )
        
        # Stream output line by line in real-time
        for line in process.stdout:
            print(line, end='', flush=True)
        
        # Wait for process to complete
        returncode = process.wait(timeout=3600)
        
        print(f"\n[ideation-debug] === END OUTPUT ===")
        print(f"[ideation-debug] Subprocess finished returncode={returncode}")
        
        if returncode != 0:
            raise RuntimeError(
                f"Ideation script exited with code {returncode}"
            )
        
        output_json_path = workshop_path.with_suffix(".json")
        print(f"[ideation-debug] Expecting ideation output at {output_json_path}")
        if not output_json_path.exists():
            raise FileNotFoundError(
                f"Ideation output not found: {output_json_path}"
            )
        
        with open(output_json_path, "r", encoding="utf-8") as f:
            raw_output = json.load(f)
        print(
            f"[ideation-debug] Loaded ideation JSON type={type(raw_output).__name__} "
            f"count={len(raw_output) if isinstance(raw_output, list) else 1}"
        )
        
        if isinstance(raw_output, dict):
            raw_ideas = [raw_output]
        elif isinstance(raw_output, list):
            raw_ideas = raw_output
        else:
            raise ValueError("Unexpected ideation output format")
        
        normalized_ideas = [
            _normalize_idea_payload(raw, defaults) for raw in raw_ideas
        ]
        print(
            f"[ideation-debug] Normalized {len(normalized_ideas)} idea(s); "
            f"first_keys={list(normalized_ideas[0].keys()) if normalized_ideas else 'n/a'}"
        )
        
        completed_at = datetime.utcnow()
        ideation_collection.update_one(
            {"_id": request_id},
            {
                "$set": {
                    "status": "COMPLETED",
                    "ideas": normalized_ideas,
                    "completedAt": completed_at,
                    "updatedAt": completed_at
                },
                "$unset": {
                    "error": ""
                }
            }
        )
        
        hypothesis_updates = {
            "ideation.status": "COMPLETED",
            "ideation.completedAt": completed_at,
            "ideation.ideas": normalized_ideas,
            "updatedAt": completed_at
        }
        if normalized_ideas:
            # Inject Additional Context into ideaJson if it exists in the hypothesis
            final_idea_json = normalized_ideas[0].copy()
            if additional_context:
                final_idea_json["Additional Context"] = additional_context
                print(f"[ideation-debug] Injected Additional Context into ideaJson")
            hypothesis_updates["ideaJson"] = final_idea_json
        
        hypotheses_collection.update_one(
            {"_id": hypothesis_id},
            {"$set": hypothesis_updates, "$unset": {"ideation.error": ""}}
        )
        
        print(f"\n✅ Ideation completed: {request_id} ({len(normalized_ideas)} ideas)\n")
        
    except Exception as e:
        error_msg = str(e)
        failed_at = datetime.utcnow()
        print(f"\n❌ Ideation failed: {error_msg}\n", file=sys.stderr)
        traceback.print_exc()
        
        ideation_collection.update_one(
            {"_id": request_id},
            {
                "$set": {
                    "status": "FAILED",
                    "failedAt": failed_at,
                    "error": error_msg,
                    "updatedAt": failed_at
                }
            }
        )
        hypotheses_collection.update_one(
            {"_id": hypothesis_id},
            {
                "$set": {
                    "ideation.status": "FAILED",
                    "ideation.failedAt": failed_at,
                    "ideation.error": error_msg,
                    "updatedAt": failed_at
                }
            }
        )


def run_experiment_pipeline(run: Dict[str, Any], mongo_client):
    global CURRENT_RUN_ID, EVENT_SEQ
    
    run_id = run["_id"]
    hypothesis_id = run["hypothesisId"]
    CURRENT_RUN_ID = run_id
    EVENT_SEQ = 0
    
    print(f"\n{'='*60}")
    print(f"🚀 Starting experiment: {run_id}")
    print(f"{'='*60}\n")
    
    # Load .env and export to os.environ to ensure child processes inherit
    if os.path.exists('.env'):
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        with open('.env') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        
        print("✓ Loaded and exported environment variables from .env")
    
    # Verify critical env vars
    if not os.environ.get('OPENAI_API_KEY'):
        raise ValueError("OPENAI_API_KEY not set - check .env file exists and contains OPENAI_API_KEY")
    
    print(f"✓ OPENAI_API_KEY verified: {os.environ.get('OPENAI_API_KEY')[:20]}...")
    
    try:
        db = mongo_client['ai-scientist']
        runs_collection = db["runs"]
        
        runs_collection.update_one(
            {"_id": run_id},
            {"$set": {"status": "RUNNING", "startedAt": datetime.utcnow()}}
        )
        
        gpu_info = get_gpu_info()
        event_emitter.run_started(
            run_id, 
            POD_ID,
            gpu_info.get("gpu_name", "unknown"),
            gpu_info.get("region", "unknown")
        )
        
        hypotheses_collection = db["hypotheses"]
        hypothesis = hypotheses_collection.find_one({"_id": hypothesis_id})
        
        if not hypothesis:
            raise ValueError(f"Hypothesis {hypothesis_id} not found")
        
        idea_text = hypothesis.get("idea", "")
        idea_json = hypothesis.get("ideaJson")
        
        if not idea_json:
            error_msg = "Hypothesis missing ideaJson. Please create hypothesis with ideaJson from the frontend."
            print(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        idea_name = idea_json.get("Name", "experiment")
        retry_count = run.get("retryCount", 0)
        
        base_pattern = f"experiments/*_{idea_name}_run_{run_id}"
        existing_dirs = sorted(Path("experiments").glob(f"*_{idea_name}_run_{run_id}"))
        
        if existing_dirs and retry_count > 0:
            idea_dir = str(existing_dirs[-1])
            print(f"📁 Reusing experiment directory (retry {retry_count}): {idea_dir}")
        else:
            date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            idea_dir = f"experiments/{date}_{idea_name}_run_{run_id}"
            os.makedirs(idea_dir, exist_ok=True)
            print(f"📁 Created experiment directory: {idea_dir}")
        
        idea_path_md = os.path.join(idea_dir, "idea.md")
        with open(idea_path_md, "w") as f:
            f.write(f"# {idea_json.get('Title', 'Experiment')}\n\n")
            f.write(idea_json.get("Experiment", idea_text))
        
        idea_path_json = os.path.join(idea_dir, "idea.json")
        with open(idea_path_json, "w") as f:
            json.dump(idea_json, f, indent=4)
        
        from ai_scientist.treesearch.bfts_utils import edit_bfts_config_file
        config_path = "bfts_config.yaml"
        idea_config_path = edit_bfts_config_file(config_path, idea_dir, idea_path_json)
        
        from experiment_monitor import ExperimentMonitor
        import threading
        
        exp_monitor = ExperimentMonitor(idea_dir, run_id, emit_event)
        monitor_stop = threading.Event()
        
        def monitor_loop():
            while not monitor_stop.is_set():
                try:
                    exp_monitor.scan_for_updates()
                    # Copy to list to avoid modification during iteration
                    plots_to_check = list(exp_monitor.uploaded_plots)
                    for plot_file in plots_to_check:
                        full_path = exp_monitor.exp_dir / plot_file
                        if full_path.exists() and plot_file not in exp_monitor.seen_files:
                            exp_monitor.seen_files.add(plot_file)
                            upload_artifact(run_id, str(full_path), "plot")
                except Exception as e:
                    print(f"Monitor error: {e}")
                    import traceback
                    traceback.print_exc()
                time.sleep(5)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        
        # Start heartbeat thread
        heartbeat_stop = threading.Event()
        def heartbeat_loop():
            """Send heartbeat every 30 seconds so backend knows worker is alive"""
            while not heartbeat_stop.is_set():
                try:
                    event_emitter.run_heartbeat(run_id)
                    emitter.flush()
                except Exception as e:
                    print(f"Heartbeat error: {e}")
                heartbeat_stop.wait(30)  # Send every 30 seconds
        
        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        print(f"💓 Heartbeat started (30s intervals)")
        
        # Create picklable event callback using partial
        experiment_event_callback = partial(_handle_experiment_event, run_id, emit_event, emitter, db)
        
        # Stage 1: Run experiments
        ensure_run_not_canceled(db, run_id)
        with StageContext("Stage_1", run_id):
            print(f"\n▶ Running Stage_1: Preliminary Investigation...")
            event_emitter.log(run_id, "Starting preliminary investigation (BFTS experiments)", "info", "Stage_1")
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage": {"name": "Stage_1", "progress": 0.0}}}
            )
            
            # Log configuration details
            import yaml
            config_path = os.path.join(os.path.dirname(__file__), "bfts_config.yaml")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    exp_config = yaml.safe_load(f)
                    max_iterations = exp_config.get("max_iterations_per_stage", {}).get("Stage_1", 5)
                    event_emitter.log(run_id, f"Max iterations for Stage_1: {max_iterations}", "info", "Stage_1")
            
            event_emitter.log(run_id, f"Loading experiment configuration from: {idea_config_path}", "info", "Stage_1")
            
            from ai_scientist.treesearch.perform_experiments_bfts_with_agentmanager import perform_experiments_bfts
            perform_experiments_bfts(idea_config_path, event_callback=experiment_event_callback)
            
            event_emitter.log(run_id, "Stage_1 experiments completed", "info", "Stage_1")
            emitter.flush()
                
        # Final progress for stage
        # This will be overridden by step_callback during execution
        
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), "bfts_config.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        writeup_config = config.get("writeup", {})
        plot_model = writeup_config.get("plot_model", "gpt-5.1")
        small_model = writeup_config.get("small_model", "gpt-5.1")
        big_model = writeup_config.get("big_model", "gpt-5.1")
        page_limit = writeup_config.get("page_limit", 8)
        
        print(f"✓ Using from config: plot={plot_model}, small={small_model}, big={big_model}, pages={page_limit}")
        
        # Stage 2: Aggregate plots
        ensure_run_not_canceled(db, run_id)
        with StageContext("Stage_2", run_id):
            print("\n▶ Running Stage_2: Baseline Tuning (Plot Aggregation)...")
            event_emitter.log(run_id, "Starting plot aggregation", "info", "Stage_2")
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage": {"name": "Stage_2", "progress": 0.0}}}
            )
            
            # Count existing plots
            plots_dir = os.path.join(idea_dir, "plots")
            existing_plots = []
            if os.path.exists(plots_dir):
                existing_plots = [f for f in os.listdir(plots_dir) if f.endswith(('.png', '.pdf', '.jpg'))]
                event_emitter.log(run_id, f"Found {len(existing_plots)} existing plots to aggregate", "info", "Stage_2")
            else:
                event_emitter.log(run_id, "No existing plots directory found", "warning", "Stage_2")
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage.progress": 0.25}}
            )

            ensure_run_not_canceled(db, run_id)
            
            print("\n📊 Aggregating plots...")
            event_emitter.log(run_id, f"Generating aggregator script using model: {plot_model}", "info", "Stage_2")
            
            from ai_scientist.perform_plotting import aggregate_plots
            aggregate_plots(base_folder=idea_dir, model=plot_model)

            ensure_run_not_canceled(db, run_id)
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage.progress": 0.75}}
            )
            
            # Count final figures
            figures_dir = os.path.join(idea_dir, "figures")
            final_figures = []
            if os.path.exists(figures_dir):
                final_figures = [f for f in os.listdir(figures_dir) if f.endswith(('.png', '.pdf', '.jpg'))]
                event_emitter.log(run_id, f"Generated {len(final_figures)} final figures", "info", "Stage_2")
                
                # Upload figures as artifacts
                for fig_file in final_figures:
                    ensure_run_not_canceled(db, run_id)
                    fig_path = os.path.join(figures_dir, fig_file)
                    if os.path.isfile(fig_path):
                        upload_artifact(run_id, fig_path, "figure")
            else:
                event_emitter.log(run_id, "Warning: No figures directory created", "warning", "Stage_2")
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage.progress": 1.0}}
            )
            
            emitter.flush()
        
        # Stage 3: Paper generation
        ensure_run_not_canceled(db, run_id)
        with StageContext("Stage_3", run_id):
            print("\n▶ Running Stage_3: Research Agenda Execution (Paper Generation)...")
            event_emitter.log(run_id, "Starting paper generation", "info", "Stage_3")
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage": {"name": "Stage_3", "progress": 0.0}}}
            )
            
            print("\n📄 Generating paper...")
            from ai_scientist.perform_icbinb_writeup import gather_citations, perform_writeup
            
            event_emitter.paper_started(run_id)
            event_emitter.log(run_id, f"Gathering citations using model: {small_model} (15 rounds)", "info", "Stage_3")
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage.progress": 0.1}}
            )
            
            citations_text = gather_citations(
                idea_dir,
                num_cite_rounds=15,
                small_model=small_model
            )
            
            citation_count = len(citations_text.split('\n')) if citations_text else 0
            event_emitter.log(run_id, f"Gathered {citation_count} lines of citations", "info", "Stage_3")
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage.progress": 0.4}}
            )

            ensure_run_not_canceled(db, run_id)
            
            event_emitter.log(run_id, f"Starting writeup generation using model: {big_model} ({page_limit} pages max)", "info", "Stage_3")
            
            try:
                writeup_success = perform_writeup(
                    base_folder=idea_dir,
                    big_model=big_model,
                    page_limit=page_limit,
                    citations_text=citations_text
                )
            except Exception as writeup_error:
                print(f"❌ CRITICAL: perform_writeup raised exception: {writeup_error}")
                event_emitter.log(run_id, f"❌ CRITICAL: Writeup exception: {str(writeup_error)[:200]}", "error", "Stage_3")
                traceback.print_exc()
                writeup_success = False

            # DIAGNOSTIC: Log writeup result explicitly
            print(f"\n{'='*60}")
            print(f"📊 DIAGNOSTIC: writeup_success = {writeup_success}")
            event_emitter.log(run_id, f"📊 DIAGNOSTIC: writeup_success = {writeup_success}", "info", "Stage_3")
            emitter.flush()  # Force flush to ensure this log is sent
            print(f"{'='*60}\n")

            ensure_run_not_canceled(db, run_id)
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage.progress": 0.8}}
            )
            
            pdf_files = []
            if writeup_success:
                event_emitter.log(run_id, "Writeup generation succeeded", "info", "Stage_3")
                print(f"\n📑 Looking for PDF files in {idea_dir}...")
                event_emitter.log(run_id, f"📑 Scanning for PDFs in: {idea_dir}", "info", "Stage_3")
                emitter.flush()
                
                try:
                    all_files = os.listdir(idea_dir)
                    pdf_files = [f for f in all_files if f.endswith(".pdf")]
                    print(f"   Found {len(pdf_files)} PDF file(s): {pdf_files}")
                    event_emitter.log(run_id, f"📑 Found {len(pdf_files)} PDFs: {pdf_files}", "info", "Stage_3")
                    emitter.flush()
                except Exception as scan_error:
                    print(f"❌ CRITICAL: Failed to scan for PDFs: {scan_error}")
                    event_emitter.log(run_id, f"❌ CRITICAL: PDF scan failed: {str(scan_error)[:200]}", "error", "Stage_3")
                    traceback.print_exc()
                    emitter.flush()
                    pdf_files = []
                
                if pdf_files:
                    # Upload ALL PDFs (reflections and final paper)
                    import shutil
                    backup_dir = Path("local_pdf_backups")
                    backup_dir.mkdir(exist_ok=True)
                    
                    # Determine if a dedicated final PDF exists
                    base_name = os.path.basename(idea_dir)
                    has_named_final = any("final" in name.lower() for name in pdf_files)
                    
                    for pdf_file in pdf_files:
                        try:
                            pdf_path = os.path.join(idea_dir, pdf_file)
                            
                            # Get PDF file size
                            ensure_run_not_canceled(db, run_id)
                            pdf_size_bytes = os.path.getsize(pdf_path)
                            pdf_size_mb = pdf_size_bytes / (1024 * 1024)
                            
                            # Determine artifact kind and whether this is the final paper
                            name_lower = pdf_file.lower()
                            is_final = ("final" in name_lower) or (
                                not has_named_final and pdf_file == f"{base_name}.pdf"
                            )
                            if "reflection" in name_lower and not is_final:
                                kind = "reflection"
                            else:
                                kind = "paper"
                            
                            event_emitter.log(run_id, f"Generated PDF: {pdf_file} ({pdf_size_mb:.2f} MB)", "info", "Stage_3")
                            
                            # Create local backup with shorter filename to avoid filesystem limits (255 chars)
                            # Use hash of original filename to keep it short while unique
                            import hashlib
                            file_hash = hashlib.md5(pdf_file.encode()).hexdigest()[:8]
                            # Extract just the suffix if present (e.g., "reflection_final_page_limit")
                            if pdf_file != f"{base_name}.pdf":
                                # Get suffix after base_name
                                suffix = pdf_file.replace(f"{base_name}", "").replace(".pdf", "")
                                backup_filename = f"{run_id}_{file_hash}{suffix}.pdf"
                            else:
                                backup_filename = f"{run_id}_paper.pdf"
                            backup_path = backup_dir / backup_filename
                            
                            print(f"   💾 Saving local backup: {backup_path}")
                            shutil.copy2(pdf_path, backup_path)
                            print(f"   ✓ Local backup saved")
                            event_emitter.log(run_id, f"Local backup saved: {backup_path}", "info", "Stage_3")
                            emitter.flush()
                            
                            print(f"   📤 Uploading {kind}: {pdf_file}")
                            event_emitter.log(run_id, f"📤 Uploading {kind} to artifact storage: {pdf_file}", "info", "Stage_3")
                            emitter.flush()
                            
                            upload_result = upload_artifact(run_id, pdf_path, kind)
                            
                            if upload_result:
                                if is_final:
                                    event_emitter.paper_generated(run_id, f"runs/{run_id}/{pdf_file}")
                                event_emitter.log(run_id, f"✅ {kind.capitalize()} uploaded successfully: {pdf_file}", "info", "Stage_3")
                            else:
                                print(f"⚠️ {kind.capitalize()} upload failed but local backup exists at {backup_path}")
                                event_emitter.log(run_id, f"⚠️ {kind.capitalize()} upload failed, but backup exists at {backup_path}", "warning", "Stage_3")
                            emitter.flush()
                        except Exception as pdf_error:
                            print(f"❌ CRITICAL: PDF processing failed for {pdf_file}: {pdf_error}")
                            event_emitter.log(run_id, f"❌ CRITICAL: PDF processing failed for {pdf_file}: {str(pdf_error)[:150]}", "error", "Stage_3")
                            traceback.print_exc()
                            emitter.flush()
                else:
                    print(f"⚠️ No PDF files found in {idea_dir} after successful writeup!")
                    event_emitter.log(run_id, "No PDF found after writeup", "error", "Stage_3")
                    emitter.flush()
            else:
                print(f"⚠️ Writeup did not succeed, skipping PDF upload")
                event_emitter.log(run_id, "Writeup generation failed - run will be marked as failed", "error", "Stage_3")
                
                # Mark run as failed since we can't produce a paper
                db['runs'].update_one(
                    {"_id": run_id},
                    {
                        "$set": {
                            "status": "FAILED",
                            "failedAt": datetime.now(timezone.utc),
                            "errorMessage": "Paper generation (Stage 3) failed - writeup did not complete successfully"
                        }
                    }
                )
                event_emitter.run_failed(run_id, "Paper generation failed")
                emitter.flush()
                return  # Don't continue to Stage 4 without a paper
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage.progress": 1.0}}
            )
            
            emitter.flush()
        
        # Stage 4: Auto-validation
        ensure_run_not_canceled(db, run_id)
        with StageContext("Stage_4", run_id):
            print("\n▶ Running Stage_4: Ablation Studies (Auto-validation)...")
            event_emitter.log(run_id, "Starting auto-validation", "info", "Stage_4")
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage": {"name": "Stage_4", "progress": 0.0}}}
            )
            
            print("\n🤖 Running auto-validation...")
            writeup_cfg = config.get("writeup", {}) or {}
            review_model = (
                writeup_cfg.get("review_model")
                or writeup_cfg.get("big_model")
                or writeup_cfg.get("small_model")
                or "gpt-5.1"
            )
            event_emitter.validation_auto_started(run_id, review_model)
            event_emitter.log(run_id, f"Using review model: {review_model}", "info", "Stage_4")
            
            from ai_scientist.perform_llm_review import perform_review, load_paper
            from ai_scientist.llm import create_client
            from ai_scientist.review_context import build_auto_review_context
            
            if pdf_files:
                # Smart PDF selection: prefer final > highest numbered > any reflection
                pdf_to_review = find_best_pdf_for_review(pdf_files)
                pdf_path = os.path.join(idea_dir, pdf_to_review)
                event_emitter.log(run_id, f"Loading paper from: {pdf_to_review}", "info", "Stage_4")
                print(f"📄 Selected PDF for review: {pdf_to_review}")
                
                db['runs'].update_one(
                    {"_id": run_id},
                    {"$set": {"currentStage.progress": 0.2}}
                )
                
                ensure_run_not_canceled(db, run_id)
                paper_content = load_paper(pdf_path)
                paper_length = len(paper_content) if paper_content else 0
                event_emitter.log(run_id, f"Loaded paper content ({paper_length} characters)", "info", "Stage_4")
                
                db['runs'].update_one(
                    {"_id": run_id},
                    {"$set": {"currentStage.progress": 0.4}}
                )
                
                ensure_run_not_canceled(db, run_id)
                review_context = build_auto_review_context(idea_dir, idea_json, paper_content or "")
                event_emitter.log(
                    run_id,
                    f"Constructed review context keys: {list(review_context.keys())}",
                    "info",
                    "Stage_4",
                )
                
                event_emitter.log(run_id, "Sending paper to LLM for review", "info", "Stage_4")
                client, client_model = create_client(review_model)
                review = perform_review(
                    paper_content,
                    client_model,
                    client,
                    context=review_context,
                    num_reviews_ensemble=3,
                    num_reflections=2,
                    temperature=0.55,
                )
                
                db['runs'].update_one(
                    {"_id": run_id},
                    {"$set": {"currentStage.progress": 0.7}}
                )
                
                ensure_run_not_canceled(db, run_id)
                # Extract verdict and score from review if available
                verdict = "fail"  # default to fail for safety
                numeric_scores: Dict[str, float] = {}
                
                if isinstance(review, dict):
                    score_fields = [
                        "Originality",
                        "Quality",
                        "Clarity",
                        "Significance",
                        "Soundness",
                        "Presentation",
                        "Contribution",
                        "Overall",
                        "Confidence",
                    ]
                    for field in score_fields:
                        value = review.get(field)
                        if isinstance(value, (int, float)):
                            numeric_scores[field] = float(value)
                    
                    overall_score = numeric_scores.get("Overall", review.get("Overall"))
                    
                    # Try to extract verdict from review (case-insensitive)
                    decision = None
                    if "verdict" in review:
                        decision = review["verdict"]
                    elif "decision" in review:
                        decision = review["decision"]
                    elif "Decision" in review:
                        decision = review["Decision"]
                    
                    # Convert decision to pass/fail
                    if decision:
                        decision_lower = str(decision).lower()
                        if decision_lower in ["accept", "pass"]:
                            verdict = "pass"
                        elif decision_lower in ["reject", "fail"]:
                            verdict = "fail"
                    
                    # Override with score-based logic if Overall score exists
                    # NeurIPS scale: 1-10 where 6+ is accept, <6 is reject
                    if overall_score is not None:
                        try:
                            score_value = float(overall_score)
                            if score_value >= 6:
                                verdict = "pass"
                            else:
                                verdict = "fail"
                            event_emitter.log(run_id, f"Overall score: {score_value}/10 → verdict: {verdict}", "info", "Stage_4")
                        except (ValueError, TypeError):
                            pass
                    
                    # Log individual scores if available
                    if numeric_scores:
                        score_summary = ", ".join([f"{k}: {v}" for k, v in numeric_scores.items()])
                        event_emitter.log(run_id, f"Review scores: {score_summary}", "info", "Stage_4")
                
                event_emitter.log(run_id, f"Validation verdict: {verdict}", "info", "Stage_4")
                
                db['runs'].update_one(
                    {"_id": run_id},
                    {"$set": {"currentStage.progress": 0.9}}
                )
                
                event_emitter.validation_auto_completed(
                    run_id,
                    verdict,
                    numeric_scores,
                    json.dumps(review) if isinstance(review, dict) else str(review)
                )
                
                event_emitter.log(run_id, "Auto-validation completed successfully", "info", "Stage_4")
            else:
                event_emitter.log(run_id, "No PDF available for validation", "error", "Stage_4")
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage.progress": 1.0}}
            )
            
            emitter.flush()
        
        runs_collection.update_one(
            {"_id": run_id},
            {"$set": {"status": "COMPLETED", "completedAt": datetime.utcnow()}}
        )
        
        # Calculate total experiment duration
        total_duration_s = int(time.time() - (run.get('startedAt').timestamp() if run.get('startedAt') else time.time()))
        event_emitter.run_completed(run_id, total_duration_s)
        
        emitter.flush()
        
        # Stop background threads
        print("\n🛑 Stopping background threads...")
        monitor_stop.set()
        heartbeat_stop.set()
        monitor_thread.join(timeout=10)
        heartbeat_thread.join(timeout=5)
        print("✓ Background threads stopped")
        
        # Copy best solutions to experiment root for easy access
        print("\n📋 Copying best solutions to experiment root...")
        event_emitter.log(run_id, "📋 Copying best solutions to experiment root...", "info", "completion")
        emitter.flush()
        
        try:
            copy_best_solutions_to_root(idea_dir)
        except Exception as copy_error:
            print(f"⚠️ Failed to copy best solutions: {copy_error}")
            event_emitter.log(run_id, f"⚠️ Failed to copy best solutions: {str(copy_error)[:100]}", "warning", "completion")
            traceback.print_exc()
        
        # Upload best code files as artifacts
        print(f"\n📦 Uploading best code artifacts...")
        event_emitter.log(run_id, "📦 Starting best code artifacts upload...", "info", "completion")
        emitter.flush()
        code_files_uploaded = 0
        for stage_num in range(1, 5):  # Stages 1-4
            code_file = f"best_code_stage_{stage_num}.py"
            code_path = os.path.join(idea_dir, code_file)
            
            if os.path.exists(code_path):
                print(f"   Uploading {code_file}...")
                upload_result = upload_artifact(run_id, code_path, "code")
                
                if upload_result:
                    code_files_uploaded += 1
                    event_emitter.log(run_id, f"Code artifact uploaded: {code_file}", "info", "completion")
                    print(f"   ✓ {code_file} uploaded")
                else:
                    event_emitter.log(run_id, f"Failed to upload {code_file}", "warning", "completion")
                    print(f"   ⚠️ {code_file} upload failed")
            else:
                print(f"   ⊘ {code_file} not found (stage may not have completed)")
        
        if code_files_uploaded > 0:
            print(f"✓ Uploaded {code_files_uploaded} code artifact(s)")
            event_emitter.log(run_id, f"Uploaded {code_files_uploaded} code artifacts", "info", "completion")
        else:
            print(f"⚠️ No code artifacts found to upload")
            event_emitter.log(run_id, "No code artifacts found", "warning", "completion")
        
        # Upload the README explaining the best solutions
        readme_path = os.path.join(idea_dir, "BEST_SOLUTIONS_README.md")
        if os.path.exists(readme_path):
            print(f"\n📄 Uploading code documentation...")
            upload_result = upload_artifact(run_id, readme_path, "documentation")
            if upload_result:
                print(f"   ✓ BEST_SOLUTIONS_README.md uploaded")
                event_emitter.log(run_id, "Code documentation uploaded", "info", "completion")
            else:
                print(f"   ⚠️ Failed to upload README")
        
        print("\n📦 Archiving experiment artifacts to MinIO...")
        event_emitter.log(run_id, "📦 Starting experiment archive upload to MinIO...", "info", "completion")
        emitter.flush()
        
        archive_uploaded = False
        try:
            import tarfile
            import tempfile
            
            print("   Creating archive...")
            with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
                archive_path = tmp.name
            
            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(idea_dir, arcname=os.path.basename(idea_dir))
                if os.path.exists('ai_scientist/ideas'):
                    tar.add('ai_scientist/ideas', arcname='ideas')
            
            archive_size = os.path.getsize(archive_path) / (1024 * 1024)
            print(f"   Archive created: {archive_size:.2f} MB")
            event_emitter.log(run_id, f"📦 Archive created: {archive_size:.2f} MB, uploading...", "info", "completion")
            emitter.flush()
            
            archive_uploaded = upload_artifact(run_id, archive_path, "archive")
            os.unlink(archive_path)
            
            if archive_uploaded:
                print(f"✓ Archived experiment to MinIO")
                event_emitter.log(run_id, "✅ Archive uploaded successfully to MinIO", "info", "completion")
                print(f"🧹 Cleaning up local experiment directory...")
                import shutil
                shutil.rmtree(idea_dir, ignore_errors=True)
                print(f"✓ Cleaned up {idea_dir}")
            else:
                print(f"⚠️ Archive upload failed - keeping local experiment directory: {idea_dir}")
                print(f"   You can manually clean up later or retry the archive upload")
                event_emitter.log(run_id, f"⚠️ Archive upload failed, keeping local: {idea_dir}", "warning", "completion")
            emitter.flush()
            
        except Exception as e:
            print(f"⚠️ Archive/cleanup failed: {e}")
            print(f"   Keeping local experiment directory: {idea_dir}")
            event_emitter.log(run_id, f"❌ Archive/cleanup exception: {str(e)[:150]}", "error", "completion")
            traceback.print_exc()
            emitter.flush()
        
        print(f"\n{'='*60}")
        print(f"✅ Experiment completed successfully: {run_id}")
        print(f"{'='*60}")
        
        # DIAGNOSTIC: Final summary of what was uploaded
        print(f"\n📊 FINAL UPLOAD SUMMARY:")
        event_emitter.log(run_id, "📊 FINAL UPLOAD SUMMARY - checking what was uploaded", "info", "completion")
        emitter.flush()
        
        summary_items = []
        summary_items.append(f"Archive uploaded: {archive_uploaded}")
        summary_items.append(f"Code files uploaded: {code_files_uploaded}")
        
        for item in summary_items:
            print(f"   • {item}")
            
        event_emitter.log(run_id, f"📊 Summary: archive={archive_uploaded}, code_files={code_files_uploaded}", "info", "completion")
        emitter.flush()
        print()
        
    except RunCanceledException as e:
        print(f"\n⚠️ Experiment canceled: {e}")
        
        db = mongo_client['ai-scientist']
        runs_collection = db["runs"]
        runs_collection.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "status": "CANCELED",
                    "canceledAt": datetime.utcnow()
                }
            }
        )
        
        event_emitter.log(run_id, "Run canceled by user", "warning", CURRENT_STAGE or "unknown")
        emit_event("ai.run.canceled", {
            "reason": "User canceled run via UI",
            "stage": CURRENT_STAGE or "unknown"
        })
        emitter.flush()
        
        if 'monitor_stop' in locals():
            monitor_stop.set()
            if 'monitor_thread' in locals():
                monitor_thread.join(timeout=5)
        if 'heartbeat_stop' in locals():
            heartbeat_stop.set()
            if 'heartbeat_thread' in locals():
                heartbeat_thread.join(timeout=5)
        
        print(f"🛑 Run {run_id} canceled; pipeline exited cleanly.")

    except Exception as e:
        print(f"\n❌ Experiment failed: {e}", file=sys.stderr)
        traceback.print_exc()
        
        db = mongo_client['ai-scientist']
        runs_collection = db["runs"]
        
        # Copy best solutions to root even on failure so they're accessible
        if 'idea_dir' in locals() and os.path.exists(idea_dir):
            print(f"\n📋 Copying best solutions to experiment root (best-effort)...")
            try:
                copy_best_solutions_to_root(idea_dir)
            except Exception as copy_err:
                print(f"⚠️ Could not copy best solutions: {copy_err}")
        
        # Try to upload experiment archive as a best-effort even on failure
        # This preserves partial results and code for debugging
        print(f"\n📦 Attempting to archive partial experiment results...")
        try:
            import tarfile
            import tempfile
            
            if 'idea_dir' in locals() and os.path.exists(idea_dir):
                with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
                    archive_path = tmp.name
                
                with tarfile.open(archive_path, 'w:gz') as tar:
                    tar.add(idea_dir, arcname=os.path.basename(idea_dir))
                    if os.path.exists('ai_scientist/ideas'):
                        tar.add('ai_scientist/ideas', arcname='ideas')
                
                archive_uploaded = upload_artifact(run_id, archive_path, "archive")
                os.unlink(archive_path)
                
                if archive_uploaded:
                    print(f"✓ Partial experiment archive uploaded to MinIO")
                else:
                    print(f"⚠️ Archive upload failed - partial results may not be retrievable")
        except Exception as archive_err:
            print(f"⚠️ Could not create/upload partial archive: {archive_err}")
        
        # First, emit the failure event before updating the database
        # This ensures the frontend gets notified immediately
        event_emitter.run_failed(
            run_id,
            CURRENT_STAGE or "unknown",
            type(e).__name__,
            str(e),
            traceback.format_exc()
        )
        emitter.flush()
        
        retry_count = run.get("retryCount", 0)
        max_retries = 0  # NO AUTO-RETRY - Stop and wait for human intervention
        
        if retry_count < max_retries:
            runs_collection.update_one(
                {"_id": run_id},
                {
                    "$set": {
                        "status": "QUEUED",
                        "claimedBy": None,
                        "retryCount": retry_count + 1,
                        "lastError": {
                            "code": type(e).__name__,
                            "message": str(e),
                            "timestamp": datetime.utcnow()
                        }
                    }
                }
            )
            print(f"🔄 Run reset to QUEUED for retry ({retry_count + 1}/{max_retries})")
        else:
            runs_collection.update_one(
                {"_id": run_id},
                {"$set": {
                    "status": "FAILED",
                    "failedAt": datetime.utcnow(),
                    "errorMessage": str(e)[:500],
                    "errorType": type(e).__name__
                }}
            )
            print(f"❌ Run FAILED - requires human intervention")
            print(f"   Error: {type(e).__name__}: {str(e)[:200]}")
        
        # Stop background threads if they were started
        if 'monitor_stop' in locals():
            monitor_stop.set()
            if 'monitor_thread' in locals():
                monitor_thread.join(timeout=5)
        
        if 'heartbeat_stop' in locals():
            heartbeat_stop.set()
            if 'heartbeat_thread' in locals():
                heartbeat_thread.join(timeout=5)


def perform_writeup_retry(run: Dict[str, Any], mongo_client):
    global CURRENT_RUN_ID, CURRENT_STAGE, EVENT_SEQ
    
    run_id = run["_id"]
    CURRENT_RUN_ID = run_id
    CURRENT_STAGE = "writeup_retry"
    EVENT_SEQ = run.get("lastEventSeq", 0)
    
    # CRITICAL: Sync event_emitter's sequence counter with the run's lastEventSeq
    # Without this, new events would have seq < lastEventSeq and be rejected by orchestrator
    event_emitter.set_seq_counter(EVENT_SEQ)
    
    print(f"\n{'='*60}")
    print(f"📝 WRITEUP RETRY: {run_id}")
    print(f"{'='*60}\n")
    
    db = mongo_client['ai-scientist']
    runs_collection = db["runs"]
    
    try:
        emit_event("ai.run.log", {
            "run_id": run_id,
            "level": "info",
            "message": "🔄 Starting paper generation retry...",
            "source": "writeup_retry"
        })
        
        experiments_dir = Path("experiments")
        experiments_dir.mkdir(exist_ok=True)
        matching_dirs = sorted([d for d in experiments_dir.iterdir() if run_id in d.name])
        
        if not matching_dirs:
            # Try to restore from MinIO archive
            print(f"📦 Experiment directory not found locally, attempting to restore from archive...")
            emit_event("ai.run.log", {
                "run_id": run_id,
                "level": "info",
                "message": "📦 Restoring experiment from MinIO archive...",
                "source": "writeup_retry"
            })
            
            try:
                # Query database for archive artifact
                artifacts_collection = db["artifacts"]
                archive_artifact = artifacts_collection.find_one({
                    "runId": run_id,
                    "key": {"$regex": "archive"}
                })
                
                if not archive_artifact:
                    raise FileNotFoundError(f"No archive artifact found for run {run_id}")
                
                archive_key = archive_artifact["key"]
                print(f"   Found archive: {archive_key}")
                
                # Download archive from MinIO
                import tempfile
                import tarfile
                
                resp = requests.post(
                    f"{CONTROL_PLANE_URL}/api/runs/{run_id}/artifacts/presign",
                    json={"action": "get", "key": archive_key},
                    timeout=30
                )
                resp.raise_for_status()
                download_url = resp.json()["url"]
                
                print(f"   Downloading archive...")
                archive_resp = requests.get(download_url, timeout=300)
                archive_resp.raise_for_status()
                
                # Extract archive
                with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
                    tmp.write(archive_resp.content)
                    tmp_path = tmp.name
                
                print(f"   Extracting archive to experiments/...")
                with tarfile.open(tmp_path, 'r:gz') as tar:
                    tar.extractall(path="experiments")
                
                os.unlink(tmp_path)
                print(f"   ✓ Archive restored successfully")
                
                # Re-scan for directories
                matching_dirs = sorted([d for d in experiments_dir.iterdir() if run_id in d.name])
                
                if not matching_dirs:
                    raise FileNotFoundError(f"Archive extracted but no matching directory found for run {run_id}")
                    
            except Exception as e:
                raise FileNotFoundError(f"Failed to restore experiment from archive: {e}")
        
        exp_dir = matching_dirs[-1]
        print(f"📂 Using experiment directory: {exp_dir}")
        
        emit_event("ai.run.log", {
            "run_id": run_id,
            "level": "info",
            "message": f"📂 Found experiment directory: {exp_dir.name}",
            "source": "writeup_retry"
        })
        
        config_path = exp_dir / "bfts_config.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, "r") as f:
            import yaml
            config = yaml.safe_load(f)
        
        writeup_config = config.get("writeup", {})
        small_model = writeup_config.get("small_model", "gpt-4o-2024-05-13")
        big_model = writeup_config.get("big_model", "o1-2024-12-17")
        num_cite_rounds = writeup_config.get("num_cite_rounds", 20)
        n_reflections = writeup_config.get("n_writeup_reflections", 3)
        page_limit = writeup_config.get("page_limit", 8)
        
        emit_event("ai.run.log", {
            "run_id": run_id,
            "level": "info",
            "message": "📊 Aggregating plots...",
            "source": "writeup_retry"
        })
        
        from ai_scientist.perform_plotting import aggregate_plots
        aggregate_plots(str(exp_dir), small_model)
        
        emit_event("ai.run.log", {
            "run_id": run_id,
            "level": "info",
            "message": "✍️  Generating paper writeup...",
            "source": "writeup_retry"
        })
        
        from ai_scientist.perform_icbinb_writeup import perform_writeup
        success = perform_writeup(
            base_folder=str(exp_dir),
            citations_text=None,
            no_writing=False,
            num_cite_rounds=num_cite_rounds,
            small_model=small_model,
            big_model=big_model,
            n_writeup_reflections=n_reflections,
            page_limit=page_limit
        )
        
        if not success:
            raise Exception("Writeup generation failed")
        
        emit_event("ai.run.log", {
            "run_id": run_id,
            "level": "info",
            "message": "✅ Paper generated successfully",
            "source": "writeup_retry"
        })
        
        pdf_files = list(exp_dir.glob("*.pdf"))
        
        if pdf_files:
            # Upload ALL PDFs (reflections and final paper)
            import shutil
            backup_dir = Path("local_pdf_backups")
            backup_dir.mkdir(exist_ok=True)
            
            # Determine if a dedicated final PDF exists
            base_name = exp_dir.name
            has_named_final = any("final" in f.name.lower() for f in pdf_files)
            
            for pdf_file in pdf_files:
                # Create shorter backup filename to avoid filesystem limits (255 chars)
                import hashlib
                file_hash = hashlib.md5(pdf_file.name.encode()).hexdigest()[:8]
                if pdf_file.name != f"{base_name}.pdf":
                    suffix = pdf_file.name.replace(f"{base_name}", "").replace(".pdf", "")
                    backup_filename = f"{run_id}_{file_hash}{suffix}.pdf"
                else:
                    backup_filename = f"{run_id}_paper.pdf"
                backup_path = backup_dir / backup_filename
                
                # Determine artifact kind and whether this is the final paper
                name_lower = pdf_file.name.lower()
                is_final = ("final" in name_lower) or (
                    not has_named_final and pdf_file.name == f"{base_name}.pdf"
                )
                if "reflection" in name_lower and not is_final:
                    kind = "reflection"
                else:
                    kind = "paper"
                
                emit_event("ai.run.log", {
                    "run_id": run_id,
                    "level": "info",
                    "message": f"💾 Saving local backup: {backup_path}",
                    "source": "writeup_retry"
                })
                
                shutil.copy2(str(pdf_file), str(backup_path))
                print(f"   ✓ Local backup saved: {backup_path}")
                
                emit_event("ai.run.log", {
                    "run_id": run_id,
                    "level": "info",
                    "message": f"📤 Uploading {kind} artifact: {pdf_file.name}",
                    "source": "writeup_retry"
                })
                
                upload_result = upload_artifact(run_id, str(pdf_file), kind)
                
                if upload_result:
                    emit_event("ai.run.log", {
                        "run_id": run_id,
                        "level": "info",
                        "message": f"✅ {kind.capitalize()} uploaded successfully: {pdf_file.name}",
                        "source": "writeup_retry"
                    })
                    if is_final:
                        event_emitter.paper_generated(run_id, f"runs/{run_id}/{pdf_file.name}")
                else:
                    emit_event("ai.run.log", {
                        "run_id": run_id,
                        "level": "warn",
                        "message": f"⚠️  Failed to upload {kind} but local backup exists at {backup_path}",
                        "source": "writeup_retry"
                    })
        else:
            print(f"⚠️  No PDF files found in {exp_dir} after successful writeup!")
            emit_event("ai.run.log", {
                "run_id": run_id,
                "level": "warn",
                "message": f"⚠️  No PDF files found after writeup",
                "source": "writeup_retry"
            })
        
        runs_collection.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "pendingWriteupRetry": False,
                    "writeupRetryCompletedAt": datetime.utcnow(),
                    "updatedAt": datetime.utcnow()
                },
                "$unset": {
                    "writeupRetryClaimedBy": "",
                    "writeupRetryClaimedAt": ""
                }
            }
        )
        
        emit_event("ai.run.log", {
            "run_id": run_id,
            "level": "info",
            "message": "✨ Writeup retry completed successfully",
            "source": "writeup_retry"
        })
        
        emitter.flush()
        print(f"\n✅ Writeup retry completed: {run_id}\n")
        
    except Exception as e:
        print(f"\n❌ Writeup retry failed: {e}", file=sys.stderr)
        traceback.print_exc()
        
        runs_collection.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "pendingWriteupRetry": False,
                    "writeupRetryFailedAt": datetime.utcnow(),
                    "writeupRetryError": str(e),
                    "updatedAt": datetime.utcnow()
                },
                "$unset": {
                    "writeupRetryClaimedBy": "",
                    "writeupRetryClaimedAt": ""
                }
            }
        )
        
        emit_event("ai.run.log", {
            "run_id": run_id,
            "level": "error",
            "message": f"❌ Writeup retry failed: {str(e)}",
            "source": "writeup_retry"
        })
        
        emitter.flush()


def main():
    parser = argparse.ArgumentParser(description="AI Scientist Pod Worker")
    default_mode = os.environ.get("WORKER_MODE", "experiment").lower()
    if default_mode not in {"experiment", "ideation", "hybrid"}:
        default_mode = "experiment"
    parser.add_argument(
        "--mode",
        choices=["experiment", "ideation", "hybrid"],
        default=default_mode,
        help="Worker task focus. 'ideation' dedicates the pod to idea generation."
    )
    args = parser.parse_args()
    mode = args.mode
    
    print(f"\n{'='*60}")
    print(f"🤖 AI Scientist Pod Worker")
    print(f"{'='*60}")
    print(f"Pod ID: {POD_ID}")
    print(f"Control Plane: {CONTROL_PLANE_URL}")
    if GIT_AUTO_PULL_ENABLED:
        print(f"Git Auto-Pull: Enabled (every {GIT_AUTO_PULL_INTERVAL}s when idle)")
        print(f"Git Branch: {GIT_AUTO_PULL_BRANCH}")
    else:
        print(f"Git Auto-Pull: Disabled")
    print(f"Mode: {mode.upper()}")
    print(f"{'='*60}\n")
    
    if not MONGODB_URL:
        print("❌ MONGODB_URL environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    mongo_client = MongoClient(MONGODB_URL)
    
    try:
        mongo_client.admin.command("ping")
        print("✓ Connected to MongoDB\n")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}", file=sys.stderr)
        sys.exit(1)
    
    if mode == "ideation":
        print("🔍 Polling for ideation tasks...\n")
    elif mode == "hybrid":
        print("🔍 Polling for ideation tasks, experiments, and writeup retries...\n")
    else:
        print("🔍 Polling for experiments and writeup retries...\n")
    
    last_git_pull_time = time.time()
    
    while True:
        try:
            task_processed = False
            
            if mode in ("ideation", "hybrid"):
                ideation = fetch_next_ideation(mongo_client, POD_ID)
                if ideation:
                    run_ideation_pipeline(ideation, mongo_client)
                    print("\n✅ Ideation task completed!")
                    print("🔄 Checking for code updates...")
                    git_pull()
                    last_git_pull_time = time.time()
                    print("\n🔍 Polling for next ideation task...")
                    task_processed = True
                    if mode == "ideation":
                        continue
            
            if not task_processed and mode in ("experiment", "hybrid"):
                run = fetch_next_experiment(mongo_client, POD_ID)
                if run:
                    run_experiment_pipeline(run, mongo_client)
                    print("\n✅ Experiment completed!")
                    print("🔄 Checking for code updates...")
                    git_pull()
                    last_git_pull_time = time.time()
                    print("\n🔍 Polling for next task...")
                    task_processed = True
                else:
                    writeup_retry = fetch_writeup_retry(mongo_client, POD_ID)
                    if writeup_retry:
                        perform_writeup_retry(writeup_retry, mongo_client)
                        print("\n✅ Writeup retry completed!")
                        print("🔄 Checking for code updates...")
                        git_pull()
                        last_git_pull_time = time.time()
                        print("\n🔍 Polling for next task...")
                        task_processed = True
            
            if task_processed:
                continue
            
            current_time = time.time()
            time_since_last_pull = current_time - last_git_pull_time
            
            if GIT_AUTO_PULL_ENABLED and time_since_last_pull >= GIT_AUTO_PULL_INTERVAL:
                git_pull()
                last_git_pull_time = current_time
            
            if mode == "ideation":
                print("⏱️  No ideation tasks available, waiting 10s...")
            elif mode == "experiment":
                print("⏱️  No experiments or retries available, waiting 10s...")
            else:
                print("⏱️  No ideation, experiment, or retry tasks available, waiting 10s...")
            time.sleep(10)
        
        except KeyboardInterrupt:
            print("\n🛑 Shutting down gracefully...")
            emitter.flush()
            break
        except Exception as e:
            print(f"❌ Worker error: {e}", file=sys.stderr)
            traceback.print_exc()
            time.sleep(30)


if __name__ == "__main__":
    main()
