import os
import sys
import time
import json
import hashlib
import traceback
import requests
import socket
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from pymongo import MongoClient, ReturnDocument
from ulid import ULID

from event_emitter import CloudEventEmitter

CONTROL_PLANE_URL = os.environ.get("CONTROL_PLANE_URL", "https://ai-scientist-v2-production.up.railway.app")
MONGODB_URL = os.environ.get("MONGODB_URL", "")
POD_ID = os.environ.get("RUNPOD_POD_ID", socket.gethostname())

CURRENT_RUN_ID: Optional[str] = None
CURRENT_STAGE: Optional[str] = None

event_emitter = CloudEventEmitter(CONTROL_PLANE_URL, POD_ID)


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
            print(f"Marking run {CURRENT_RUN_ID} as CANCELLED...")
            from pymongo import MongoClient
            client = MongoClient(MONGODB_URL)
            db = client['ai-scientist']
            db['runs'].update_one(
                {'_id': CURRENT_RUN_ID},
                {'$set': {
                    'status': 'CANCELLED',
                    'cancelledAt': datetime.utcnow()
                }}
            )
            
            emit_event("ai.run.cancelled", {
                "run_id": CURRENT_RUN_ID,
                "reason": f"Worker received {sig_name}",
                "stage": CURRENT_STAGE or "unknown"
            })
            emitter.flush()
            print(f"✓ Run marked as CANCELLED")
    except Exception as e:
        print(f"Failed to mark run as cancelled: {e}")
    
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
            emit_event("ai.run.failed", {
                "run_id": self.run_id,
                "stage": self.stage,
                "code": exc_type.__name__,
                "message": str(exc_value),
                "traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
                "retryable": is_retryable(exc_type)
            })
            emitter.flush()
            return False
        
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
        # TODO: Consider using batched emitter instead of CloudEventEmitter for reliability
        # CloudEventEmitter sends immediately and failures may be lost
        success = event_emitter.stage_completed(
            self.run_id,
            self.stage,
            int(duration_s)
        )
        
        if success:
            print(f"✓ Stage {self.stage} completed in {int(duration_s)}s")
        else:
            print(f"⚠️ Failed to emit stage_completed event for {self.stage}")
            # Also try with batched emitter as fallback
            emit_event("ai.run.stage_completed", {
                "run_id": self.run_id,
                "stage": self.stage,
                "duration_s": int(duration_s)
            })
            emitter.flush()
        
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
        
        def experiment_event_callback(event_type: str, data: dict):
            data["run_id"] = run_id
            emit_event(event_type, data)
            emitter.flush()
            
            # Update MongoDB currentStage when internal BFTS stages progress
            if event_type == "ai.run.stage_progress":
                try:
                    internal_stage = data.get("stage", "")
                    progress = data.get("progress", 0.0)
                    iteration = data.get("iteration", 0)
                    max_iterations = data.get("max_iterations", 1)
                    good_nodes = data.get("good_nodes", 0)
                    buggy_nodes = data.get("buggy_nodes", 0)
                    total_nodes = data.get("total_nodes", 0)
                    
                    # Map internal BFTS stage names to user-friendly names
                    # Format from perform_experiments_bfts: "1_initial", "2_baseline", "3_creative", "4_ablation"
                    stage_display_names = {
                        "1_initial": "Stage 1: Initial Implementation",
                        "2_baseline": "Stage 2: Baseline Tuning",
                        "3_creative": "Stage 3: Creative Research",
                        "4_ablation": "Stage 4: Ablation Studies",
                        # Legacy formats just in case
                        "stage_1": "Stage 1: Initial Implementation",
                        "stage_2": "Stage 2: Baseline Tuning",
                        "stage_3": "Stage 3: Creative Research",
                        "stage_4": "Stage 4: Ablation Studies"
                    }
                    
                    display_name = stage_display_names.get(internal_stage, f"Stage: {internal_stage}")
                    
                    print(f"🔄 Updating UI: {display_name} - {progress*100:.1f}% ({good_nodes}/{total_nodes} nodes)")
                    
                    db['runs'].update_one(
                        {"_id": run_id},
                        {"$set": {
                            "currentStage": {
                                "name": display_name,
                                "progress": progress,
                                "iteration": iteration,
                                "maxIterations": max_iterations,
                                "goodNodes": good_nodes,
                                "buggyNodes": buggy_nodes,
                                "totalNodes": total_nodes,
                                "bestMetric": data.get("best_metric")
                            }
                        }}
                    )
                except Exception as e:
                    print(f"Failed to update currentStage in MongoDB: {e}")
                    import traceback
                    traceback.print_exc()
        
        # Stage 1: Run experiments
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
        
        plot_model = config.get("writeup", {}).get("plot_model", "gpt-5-mini")
        small_model = config.get("writeup", {}).get("small_model", "gpt-5-mini")
        big_model = config.get("writeup", {}).get("big_model", "gpt-5")
        
        print(f"✓ Using models from config: plot={plot_model}, small={small_model}, big={big_model}")
        
        # Stage 2: Aggregate plots
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
            
            print("\n📊 Aggregating plots...")
            event_emitter.log(run_id, f"Generating aggregator script using model: {plot_model}", "info", "Stage_2")
            
            from ai_scientist.perform_plotting import aggregate_plots
            aggregate_plots(base_folder=idea_dir, model=plot_model)
            
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
            
            event_emitter.log(run_id, f"Starting writeup generation using model: {big_model} (4 pages max)", "info", "Stage_3")
            
            writeup_success = perform_writeup(
                base_folder=idea_dir,
                big_model=big_model,
                page_limit=4,
                citations_text=citations_text
            )
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage.progress": 0.8}}
            )
            
            pdf_files = []
            if writeup_success:
                event_emitter.log(run_id, "Writeup generation succeeded", "info", "Stage_3")
                print(f"\n📑 Looking for PDF files in {idea_dir}...")
                all_files = os.listdir(idea_dir)
                pdf_files = [f for f in all_files if f.endswith(".pdf")]
                print(f"   Found {len(pdf_files)} PDF file(s): {pdf_files}")
                
                if pdf_files:
                    # Upload ALL PDFs (reflections and final paper)
                    import shutil
                    backup_dir = Path("local_pdf_backups")
                    backup_dir.mkdir(exist_ok=True)
                    
                    # Determine if a dedicated final PDF exists
                    base_name = os.path.basename(idea_dir)
                    has_named_final = any("final" in name.lower() for name in pdf_files)
                    
                    for pdf_file in pdf_files:
                        pdf_path = os.path.join(idea_dir, pdf_file)
                        
                        # Get PDF file size
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
                        
                        # Create local backup
                        backup_filename = f"{run_id}_{pdf_file}"
                        backup_path = backup_dir / backup_filename
                        
                        print(f"   💾 Saving local backup: {backup_path}")
                        shutil.copy2(pdf_path, backup_path)
                        print(f"   ✓ Local backup saved")
                        event_emitter.log(run_id, f"Local backup saved: {backup_path}", "info", "Stage_3")
                        
                        print(f"   Uploading {kind}: {pdf_file}")
                        event_emitter.log(run_id, f"Uploading {kind} to artifact storage", "info", "Stage_3")
                        upload_result = upload_artifact(run_id, pdf_path, kind)
                        
                        if upload_result:
                            if is_final:
                                event_emitter.paper_generated(run_id, f"runs/{run_id}/{pdf_file}")
                            event_emitter.log(run_id, f"{kind.capitalize()} uploaded successfully: {pdf_file}", "info", "Stage_3")
                        else:
                            print(f"⚠️ {kind.capitalize()} upload failed but local backup exists at {backup_path}")
                            event_emitter.log(run_id, f"{kind.capitalize()} upload failed, but backup exists at {backup_path}", "warning", "Stage_3")
                else:
                    print(f"⚠️ No PDF files found in {idea_dir} after successful writeup!")
                    event_emitter.log(run_id, "No PDF found after writeup", "error", "Stage_3")
            else:
                print(f"⚠️ Writeup did not succeed, skipping PDF upload")
                event_emitter.log(run_id, "Writeup generation failed", "error", "Stage_3")
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage.progress": 1.0}}
            )
            
            emitter.flush()
        
        # Stage 4: Auto-validation
        with StageContext("Stage_4", run_id):
            print("\n▶ Running Stage_4: Ablation Studies (Auto-validation)...")
            event_emitter.log(run_id, "Starting auto-validation", "info", "Stage_4")
            
            db['runs'].update_one(
                {"_id": run_id},
                {"$set": {"currentStage": {"name": "Stage_4", "progress": 0.0}}}
            )
            
            print("\n🤖 Running auto-validation...")
            review_model = config.get("writeup", {}).get("small_model", "gpt-5-mini")
            event_emitter.validation_auto_started(run_id, review_model)
            event_emitter.log(run_id, f"Using review model: {review_model}", "info", "Stage_4")
            
            from ai_scientist.perform_llm_review import perform_review, load_paper
            from ai_scientist.llm import create_client
            
            if pdf_files:
                pdf_path = os.path.join(idea_dir, pdf_files[0])
                event_emitter.log(run_id, f"Loading paper from: {pdf_files[0]}", "info", "Stage_4")
                
                db['runs'].update_one(
                    {"_id": run_id},
                    {"$set": {"currentStage.progress": 0.2}}
                )
                
                paper_content = load_paper(pdf_path)
                paper_length = len(paper_content) if paper_content else 0
                event_emitter.log(run_id, f"Loaded paper content ({paper_length} characters)", "info", "Stage_4")
                
                db['runs'].update_one(
                    {"_id": run_id},
                    {"$set": {"currentStage.progress": 0.4}}
                )
                
                event_emitter.log(run_id, "Sending paper to LLM for review", "info", "Stage_4")
                client, client_model = create_client(review_model)
                review = perform_review(paper_content, client_model, client)
                
                db['runs'].update_one(
                    {"_id": run_id},
                    {"$set": {"currentStage.progress": 0.7}}
                )
                
                # Extract verdict and score from review if available
                verdict = "fail"  # default to fail for safety
                scores = {}
                
                if isinstance(review, dict):
                    # Extract scores first
                    if "scores" in review:
                        scores = review["scores"]
                    elif "score" in review:
                        scores = {"overall": review["score"]}
                    
                    # Extract numeric scores for decision logic
                    overall_score = review.get("Overall")
                    
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
                    if isinstance(scores, dict):
                        score_summary = ", ".join([f"{k}: {v}" for k, v in scores.items()])
                        event_emitter.log(run_id, f"Review scores: {score_summary}", "info", "Stage_4")
                
                event_emitter.log(run_id, f"Validation verdict: {verdict}", "info", "Stage_4")
                
                db['runs'].update_one(
                    {"_id": run_id},
                    {"$set": {"currentStage.progress": 0.9}}
                )
                
                event_emitter.validation_auto_completed(
                    run_id,
                    verdict,
                    scores,
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
        copy_best_solutions_to_root(idea_dir)
        
        print("\n📦 Archiving experiment artifacts to MinIO...")
        archive_uploaded = False
        try:
            import tarfile
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
                archive_path = tmp.name
            
            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(idea_dir, arcname=os.path.basename(idea_dir))
                if os.path.exists('ai_scientist/ideas'):
                    tar.add('ai_scientist/ideas', arcname='ideas')
            
            archive_uploaded = upload_artifact(run_id, archive_path, "archive")
            os.unlink(archive_path)
            
            if archive_uploaded:
                print(f"✓ Archived experiment to MinIO")
                print(f"🧹 Cleaning up local experiment directory...")
                import shutil
                shutil.rmtree(idea_dir, ignore_errors=True)
                print(f"✓ Cleaned up {idea_dir}")
            else:
                print(f"⚠️ Archive upload failed - keeping local experiment directory: {idea_dir}")
                print(f"   You can manually clean up later or retry the archive upload")
            
        except Exception as e:
            print(f"⚠️ Archive/cleanup failed: {e}")
            print(f"   Keeping local experiment directory: {idea_dir}")
            traceback.print_exc()
        
        print(f"\n{'='*60}")
        print(f"✅ Experiment completed successfully: {run_id}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ Experiment failed: {e}", file=sys.stderr)
        traceback.print_exc()
        
        db = mongo_client['ai-scientist']
        runs_collection = db["runs"]
        
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
        
        event_emitter.run_failed(
            run_id,
            CURRENT_STAGE or "unknown",
            type(e).__name__,
            str(e),
            traceback.format_exc()
        )
        emitter.flush()
        
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
        page_limit = writeup_config.get("page_limit", 4)
        
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
                backup_filename = f"{run_id}_{pdf_file.name}"
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
    print(f"\n{'='*60}")
    print(f"🤖 AI Scientist Pod Worker")
    print(f"{'='*60}")
    print(f"Pod ID: {POD_ID}")
    print(f"Control Plane: {CONTROL_PLANE_URL}")
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
    
    print("🔍 Polling for experiments and writeup retries...\n")
    
    while True:
        try:
            run = fetch_next_experiment(mongo_client, POD_ID)
            
            if run:
                run_experiment_pipeline(run, mongo_client)
                print("\n🔍 Experiment completed, polling for next task...")
            else:
                writeup_retry = fetch_writeup_retry(mongo_client, POD_ID)
                if writeup_retry:
                    perform_writeup_retry(writeup_retry, mongo_client)
                    print("\n🔍 Writeup retry completed, polling for next task...")
                else:
                    print(f"⏱️  No experiments or retries available, waiting 10s...")
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

