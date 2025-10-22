# Slack Integration Setup Guide

This guide will help you set up the `/research` slash command in Slack to trigger AI Scientist experiments.

## Architecture

```
Slack → Port Forward → FastAPI Server → MongoDB + Launch Experiment
```

## Prerequisites

1. **MongoDB** running locally or remotely
2. **Python environment** with dependencies installed
3. **Slack workspace** with admin permissions
4. **Port forwarding tool** (ngrok, localtunnel, or Slack CLI)

## Setup Steps

### 1. Install Dependencies

All required dependencies should already be in `requirements.txt`:
- `fastapi`
- `uvicorn[standard]`
- `pymongo`

If not installed yet:
```bash
source .venv/bin/activate
pip install fastapi uvicorn[standard] pymongo
```

### 2. Set Up MongoDB

#### Option A: Local MongoDB
```bash
# Install MongoDB (macOS)
brew install mongodb-community

# Start MongoDB
brew services start mongodb-community

# Verify it's running
mongosh  # Should connect to mongodb://localhost:27017
```

#### Option B: MongoDB Atlas (Cloud)
1. Sign up at https://www.mongodb.com/cloud/atlas
2. Create a free cluster
3. Get your connection string
4. Update `.env` with your MongoDB URI

### 3. Configure Environment Variables

Create a `.env` file in the project root:
```bash
cp .env.example .env
```

Edit `.env`:
```env
MONGODB_URI=mongodb://localhost:27017/
MONGO_DB_NAME=ai_scientist
MONGO_COLLECTION=experiments
SLACK_VERIFICATION_TOKEN=your_token_here  # Get this from Slack in step 5
PORT=8000
```

### 4. Start the FastAPI Server

```bash
source .venv/bin/activate
python ai_scientist/dashboard/slack_api.py
```

The server will start on `http://localhost:8000`

You should see:
```
Starting Slack API server on port 8000
MongoDB URI: mongodb://localhost:27017/
Slack endpoint will be at: http://localhost:8000/slack/research
```

### 5. Test the Server Locally

In a new terminal:
```bash
source .venv/bin/activate
python test_slack_endpoint.py
```

This will run a test suite to verify:
- Health check works
- MongoDB connection works
- Slash command endpoint works
- Error handling works

### 6. Set Up Port Forwarding

You need to expose your local server to the internet so Slack can reach it.

#### Option A: ngrok (Recommended)
```bash
# Install ngrok
brew install ngrok

# Start ngrok
ngrok http 8000
```

You'll get a URL like: `https://abc123.ngrok.io`

Your Slack Request URL will be: `https://abc123.ngrok.io/slack/research`

#### Option B: Cloudflare Tunnel
```bash
# Install cloudflared
brew install cloudflared

# Start tunnel
cloudflared tunnel --url http://localhost:8000
```

#### Option C: VS Code Port Forwarding
If using VS Code, you can use the built-in port forwarding:
1. Open the "Ports" tab in VS Code
2. Forward port 8000
3. Set visibility to "Public"
4. Use the forwarded URL

### 7. Create Slack App

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. Name: "AI Scientist"
4. Choose your workspace
5. Click **"Create App"**

### 8. Configure Slash Command

1. In your Slack app settings, go to **"Slash Commands"**
2. Click **"Create New Command"**
3. Fill in:
   - **Command**: `/research`
   - **Request URL**: `https://your-ngrok-url.ngrok.io/slack/research`
   - **Short Description**: `Launch an AI research experiment`
   - **Usage Hint**: `[idea_name] [attempt_id=0] [model=o1-preview]`
4. Click **"Save"**

### 9. Get Verification Token (Optional but Recommended)

1. Go to **"Basic Information"** in your Slack app settings
2. Scroll to **"App Credentials"**
3. Copy the **"Verification Token"**
4. Add it to your `.env` file:
   ```env
   SLACK_VERIFICATION_TOKEN=your_actual_token_here
   ```
5. Restart the FastAPI server

### 10. Install App to Workspace

1. Go to **"Install App"** in the sidebar
2. Click **"Install to Workspace"**
3. Authorize the app
4. **Important**: You need to reinstall the app after adding the slash command!

### 11. Test the Integration

In your Slack workspace:

```
/research energy_guided_self_models
```

Or with parameters:
```
/research energy_guided_self_models attempt_id=1 model_writeup=o3-mini-2025-01-31
```

You should see a formatted response with:
- 🚀 Experiment started
- Idea name
- Attempt ID
- Model being used
- MongoDB experiment ID
- Who started it

## Usage Examples

### Basic usage:
```
/research energy_guided_self_models
```

### With attempt ID:
```
/research energy_guided_self_models attempt_id=2
```

### With custom model:
```
/research i_cant_believe_its_not_better model_writeup=o1-preview-2024-09-12
```

### All parameters:
```
/research my_idea attempt_id=3 model_writeup=o3-mini writeup_type=normal load_code=true
```

## Available Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `attempt_id` | int | 0 | Attempt number for this idea |
| `model_writeup` | string | o1-preview-2024-09-12 | Model for paper writing |
| `model_citation` | string | gpt-4o-2024-11-20 | Model for citations |
| `model_review` | string | gpt-4o-2024-11-20 | Model for review |
| `model_agg_plots` | string | o3-mini-2025-01-31 | Model for plot aggregation |
| `writeup_type` | string | icbinb | Type of writeup (icbinb/normal) |
| `add_dataset_ref` | bool | false | Add HuggingFace dataset reference |
| `load_code` | bool | false | Load .py with same name |
| `num_cite_rounds` | int | 20 | Number of citation rounds |

## Monitoring

### Check experiment logs:
```bash
tail -f /tmp/pipeline_energy_guided_self_models_attempt_0.log
```

### Query MongoDB:
```bash
mongosh

use ai_scientist
db.experiments.find().pretty()
```

### API Endpoints:

**Health check:**
```bash
curl http://localhost:8000/health
```

**List experiments:**
```bash
curl http://localhost:8000/experiments?limit=5
```

**Get specific experiment:**
```bash
curl http://localhost:8000/experiments/<experiment_id>
```

**Filter by status:**
```bash
curl http://localhost:8000/experiments?status=running
```

**Filter by user:**
```bash
curl http://localhost:8000/experiments?user=jessica
```

## Troubleshooting

### Server won't start
- Check if port 8000 is already in use: `lsof -i :8000`
- Try a different port: `PORT=8001 python ai_scientist/dashboard/slack_api.py`

### MongoDB connection error
- Verify MongoDB is running: `brew services list`
- Check connection string in `.env`
- Try connecting with mongosh: `mongosh`

### Slack command not working
- Verify ngrok is still running (ngrok URLs expire)
- Check Request URL in Slack app settings
- Look at server logs for errors
- Make sure you reinstalled the Slack app after adding the command

### "Idea not found" error
- List available ideas: `ls ai_scientist/ideas/`
- Make sure you're using the filename without extension
- Check if the idea exists as `.json` or `.md`

### Verification token error
- Get token from Slack app "Basic Information" page
- Update `.env` with correct token
- Restart the server
- Or remove token check by leaving `SLACK_VERIFICATION_TOKEN` empty

## Security Considerations

1. **Verification Token**: Always use the verification token in production
2. **HTTPS Only**: Slack requires HTTPS (ngrok/cloudflared provide this)
3. **Rate Limiting**: Consider adding rate limiting for production
4. **MongoDB Security**: Use authentication and SSL for production MongoDB
5. **Firewall**: Only expose the API port, not MongoDB port

## Next Steps

- Add experiment status updates to Slack
- Create a dashboard showing MongoDB experiments
- Add experiment cancellation
- Add notifications when experiments complete
- Integrate with Streamlit dashboard

