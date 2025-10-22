"""
Slack Integration API for AI Scientist
Handles Slack slash commands to create experiments.
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse
import pymongo
from pymongo import MongoClient

# Load environment variables from .env file
load_dotenv()

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_scientist.dashboard.utils import spawn_pipeline

app = FastAPI(title="AI Scientist Slack Integration")

# MongoDB setup
# Support both MONGODB_URI and MONGODB_URL for flexibility
MONGODB_URI = os.getenv("MONGODB_URI") or os.getenv("MONGODB_URL", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "ai_scientist")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "experiments")

# Slack verification token (optional but recommended)
SLACK_VERIFICATION_TOKEN = os.getenv("SLACK_VERIFICATION_TOKEN", "")


def get_mongo_collection():
    """Get MongoDB collection for experiments."""
    # Set a timeout to prevent Slack from timing out (Slack has 3s timeout)
    client = MongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=2000,  # 2 second timeout
        connectTimeoutMS=2000,
        socketTimeoutMS=2000
    )
    db = client[MONGO_DB_NAME]
    return db[MONGO_COLLECTION]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "AI Scientist Slack Integration"}


@app.get("/health")
async def health():
    """Health check with MongoDB connection test."""
    try:
        collection = get_mongo_collection()
        # Try to ping the database
        collection.database.client.admin.command('ping')
        return {
            "status": "healthy",
            "mongodb": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "mongodb": "disconnected",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@app.post("/slack/research")
async def slack_research_command(
    request: Request,
    token: str = Form(...),
    team_id: str = Form(...),
    team_domain: str = Form(...),
    channel_id: str = Form(...),
    channel_name: str = Form(...),
    user_id: str = Form(...),
    user_name: str = Form(...),
    command: str = Form(...),
    text: str = Form(...),
    response_url: str = Form(...),
    trigger_id: str = Form(...)
):
    """
    Handle /research slash command from Slack.
    Responds immediately and saves to MongoDB in background.
    """
    
    # Log all the inputs to console
    print("=" * 60)
    print("Slack Command Received!")
    print("=" * 60)
    print(f"Command: {command}")
    print(f"Text: {text}")
    print(f"User: {user_name} ({user_id})")
    print(f"Channel: {channel_name} ({channel_id})")
    print(f"Team: {team_domain} ({team_id})")
    print("=" * 60)
    
    # Respond to Slack immediately (within 3 seconds)
    import asyncio
    
    # Save to MongoDB in background
    asyncio.create_task(save_to_mongodb_async(
        url=text.strip() if text else None,
        user_id=user_id,
        user_name=user_name,
        channel_id=channel_id,
        channel_name=channel_name,
        team_id=team_id,
        team_domain=team_domain,
        command=command
    ))
    
    # Return success message immediately (only visible to user)
    return {
        "response_type": "ephemeral",  # Only visible to the user
        "text": f"✅ The chat log was successfully added to the queue\n\nChat: {text}"
    }


async def save_to_mongodb_async(
    url: str,
    user_id: str,
    user_name: str,
    channel_id: str,
    channel_name: str,
    team_id: str,
    team_domain: str,
    command: str
):
    """Save data to MongoDB asynchronously."""
    try:
        import time
        start_time = time.time()
        
        collection = get_mongo_collection()
        
        doc = {
            "url": url,
            "user_id": user_id,
            "user_name": user_name,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "team_id": team_id,
            "team_domain": team_domain,
            "command": command,
            "created_at": datetime.utcnow(),
        }
        
        result = collection.insert_one(doc)
        mongo_id = str(result.inserted_id)
        
        elapsed = time.time() - start_time
        print(f"✓ Saved to MongoDB with ID: {mongo_id} (took {elapsed:.2f}s)")
        
    except Exception as e:
        error_msg = str(e)
        print(f"✗ MongoDB error: {error_msg}")
        # Note: Can't notify user here since we already responded to Slack


@app.get("/experiments")
async def list_experiments(
    limit: int = 10,
    status: Optional[str] = None,
    user: Optional[str] = None
):
    """
    List experiments from MongoDB.
    
    Query parameters:
    - limit: Number of experiments to return (default: 10)
    - status: Filter by status (queued, running, completed, failed)
    - user: Filter by Slack username
    """
    try:
        collection = get_mongo_collection()
        
        # Build query
        query = {}
        if status:
            query["status"] = status
        if user:
            query["created_by_slack_user"] = user
        
        # Fetch experiments
        experiments = list(
            collection.find(query)
            .sort("created_at", pymongo.DESCENDING)
            .limit(limit)
        )
        
        # Convert ObjectId to string for JSON serialization
        for exp in experiments:
            exp["_id"] = str(exp["_id"])
            if "created_at" in exp:
                exp["created_at"] = exp["created_at"].isoformat()
            if "started_at" in exp:
                exp["started_at"] = exp["started_at"].isoformat()
            if "completed_at" in exp:
                exp["completed_at"] = exp["completed_at"].isoformat()
        
        return {
            "total": len(experiments),
            "experiments": experiments
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str):
    """Get a specific experiment by ID."""
    try:
        from bson import ObjectId
        collection = get_mongo_collection()
        
        experiment = collection.find_one({"_id": ObjectId(experiment_id)})
        
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        # Convert ObjectId to string
        experiment["_id"] = str(experiment["_id"])
        if "created_at" in experiment:
            experiment["created_at"] = experiment["created_at"].isoformat()
        if "started_at" in experiment:
            experiment["started_at"] = experiment["started_at"].isoformat()
        if "completed_at" in experiment:
            experiment["completed_at"] = experiment["completed_at"].isoformat()
        
        return experiment
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    print(f"Starting Slack API server on port {port}")
    print(f"MongoDB URI: {MONGODB_URI}")
    print(f"Slack endpoint will be at: http://localhost:{port}/slack/research")
    print(f"🔄 Auto-reload: ENABLED")
    
    # Use import string for reload to work
    uvicorn.run(
        "ai_scientist.dashboard.slack_api:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )

