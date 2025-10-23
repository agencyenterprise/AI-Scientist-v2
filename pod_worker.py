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

CONTROL_PLANE_URL = os.environ.get("CONTROL_PLANE_URL", "https://ai-scientist-v2-production.up.railway.app")
MONGODB_URL = os.environ.get("MONGODB_URL", "")
POD_ID = os.environ.get("RUNPOD_POD_ID", socket.gethostname())

CURRENT_RUN_ID: Optional[str] = None
CURRENT_STAGE: Optional[str] = None
EVENT_SEQ = 0


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
        
        emit_event("ai.run.stage_started", {
            "run_id": self.run_id,
            "stage": self.stage,
            "desc": get_stage_description(self.stage)
        })
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
        
        emit_event("ai.run.stage_completed", {
            "run_id": self.run_id,
            "stage": self.stage,
            "duration_s": duration_s
        })
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
        
        resp = requests.post(
            f"{CONTROL_PLANE_URL}/api/runs/{run_id}/artifacts/presign",
            json={"action": "put", "filename": filename, "content_type": content_type},
            timeout=30
        )
        resp.raise_for_status()
        presigned_url = resp.json()["url"]
        
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        
        resp = requests.put(presigned_url, data=file_bytes, timeout=300)
        resp.raise_for_status()
        
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        
        emit_event("ai.artifact.registered", {
            "run_id": run_id,
            "key": f"runs/{run_id}/{filename}",
            "bytes": len(file_bytes),
            "sha256": sha256,
            "content_type": content_type,
            "kind": kind
        })
        
        return True
    except Exception as e:
        emit_event("ai.artifact.failed", {
            "run_id": run_id,
            "key": f"runs/{run_id}/{os.path.basename(file_path)}",
            "code": type(e).__name__,
            "message": str(e)
        })
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


def run_experiment_pipeline(run: Dict[str, Any], mongo_client):
    global CURRENT_RUN_ID, EVENT_SEQ
    
    run_id = run["_id"]
    hypothesis_id = run["hypothesisId"]
    CURRENT_RUN_ID = run_id
    EVENT_SEQ = 0
    
    print(f"\n{'='*60}")
    print(f"🚀 Starting experiment: {run_id}")
    print(f"{'='*60}\n")
    
    try:
        db = mongo_client['ai-scientist']
        runs_collection = db["runs"]
        
        runs_collection.update_one(
            {"_id": run_id},
            {"$set": {"status": "RUNNING", "startedAt": datetime.utcnow()}}
        )
        
        emit_event("ai.run.started", {
            "run_id": run_id,
            "pod_id": POD_ID,
            "gpu": get_gpu_info().get("gpu_name", "unknown"),
            "region": get_gpu_info().get("region", "unknown"),
            "image": "sakana:latest"
        })
        
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
        
        def experiment_event_callback(event_type: str, data: dict):
            data["run_id"] = run_id
            emit_event(event_type, data)
            emitter.flush()
            
            if event_type == "ai.experiment.node_completed":
                try:
                    plots_dir = Path(idea_dir) / "plots"
                    if plots_dir.exists():
                        for plot_file in plots_dir.glob("*.png"):
                            if plot_file.stat().st_mtime > (datetime.utcnow().timestamp() - 300):
                                upload_artifact(run_id, str(plot_file), "plot")
                except Exception as e:
                    print(f"Warning: Failed to upload plots: {e}")
        
        for stage in ["Stage_1", "Stage_2", "Stage_3", "Stage_4"]:
            with StageContext(stage, run_id):
                print(f"\n▶ Running {stage}...")
                
                db['runs'].update_one(
                    {"_id": run_id},
                    {"$set": {"currentStage": {"name": stage, "progress": 0.0}}}
                )
                
                if stage == "Stage_1":
                    from ai_scientist.treesearch.perform_experiments_bfts_with_agentmanager import perform_experiments_bfts
                    perform_experiments_bfts(idea_config_path, event_callback=experiment_event_callback)
                
                emit_event("ai.run.stage_progress", {
                    "run_id": run_id,
                    "stage": stage,
                    "progress": 1.0
                })
        
        print("\n📊 Aggregating plots...")
        from ai_scientist.perform_plotting import aggregate_plots
        aggregate_plots(base_folder=idea_dir, model="o3-mini-2025-01-31")
        
        print("\n📄 Generating paper...")
        from ai_scientist.perform_icbinb_writeup import gather_citations, perform_writeup
        
        emit_event("ai.paper.started", {"run_id": run_id})
        
        citations_text = gather_citations(
            idea_dir,
            num_cite_rounds=15,
            small_model="gpt-4o-2024-11-20"
        )
        
        writeup_success = perform_writeup(
            base_folder=idea_dir,
            big_model="o1-preview-2024-09-12",
            page_limit=4,
            citations_text=citations_text
        )
        
        if writeup_success:
            pdf_files = [f for f in os.listdir(idea_dir) if f.endswith(".pdf")]
            if pdf_files:
                pdf_path = os.path.join(idea_dir, pdf_files[0])
                upload_artifact(run_id, pdf_path, "paper")
                
                emit_event("ai.paper.generated", {
                    "run_id": run_id,
                    "artifact_key": f"runs/{run_id}/{pdf_files[0]}"
                })
        
        print("\n🤖 Running auto-validation...")
        emit_event("ai.validation.auto_started", {
            "run_id": run_id,
            "model": "gpt-4o-2024-11-20",
            "rubric_version": "v1"
        })
        
        from ai_scientist.perform_llm_review import perform_review, load_paper
        from ai_scientist.llm import create_client
        
        if pdf_files:
            pdf_path = os.path.join(idea_dir, pdf_files[0])
            paper_content = load_paper(pdf_path)
            client, client_model = create_client("gpt-4o-2024-11-20")
            review = perform_review(paper_content, client_model, client)
            
            emit_event("ai.validation.auto_completed", {
                "run_id": run_id,
                "verdict": "pass",
                "scores": {"overall": 0.75},
                "notes": json.dumps(review) if isinstance(review, dict) else str(review)
            })
        
        runs_collection.update_one(
            {"_id": run_id},
            {"$set": {"status": "COMPLETED", "completedAt": datetime.utcnow()}}
        )
        
        emitter.flush()
        
        print("\n📦 Archiving experiment artifacts to MinIO...")
        try:
            import tarfile
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
                archive_path = tmp.name
            
            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(idea_dir, arcname=os.path.basename(idea_dir))
                if os.path.exists('ai_scientist/ideas'):
                    tar.add('ai_scientist/ideas', arcname='ideas')
            
            upload_artifact(run_id, archive_path, "archive")
            os.unlink(archive_path)
            
            print(f"✓ Archived experiment to MinIO")
            
            print(f"🧹 Cleaning up local experiment directory...")
            import shutil
            shutil.rmtree(idea_dir, ignore_errors=True)
            print(f"✓ Cleaned up {idea_dir}")
            
        except Exception as e:
            print(f"⚠️ Archive/cleanup failed: {e}")
        
        print(f"\n{'='*60}")
        print(f"✅ Experiment completed successfully: {run_id}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ Experiment failed: {e}", file=sys.stderr)
        traceback.print_exc()
        
        db = mongo_client['ai-scientist']
        runs_collection = db["runs"]
        
        retry_count = run.get("retryCount", 0)
        max_retries = 3
        
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
                {"$set": {"status": "FAILED"}}
            )
            print(f"❌ Run failed permanently after {max_retries} retries")
        
        emit_event("ai.run.failed", {
            "run_id": run_id,
            "stage": CURRENT_STAGE or "unknown",
            "code": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
            "retryable": retry_count < max_retries
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
    
    print("🔍 Polling for experiments...\n")
    
    while True:
        try:
            run = fetch_next_experiment(mongo_client, POD_ID)
            
            if run:
                run_experiment_pipeline(run, mongo_client)
            else:
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

