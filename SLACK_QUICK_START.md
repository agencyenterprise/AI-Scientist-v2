# Slack Integration - Quick Start

## TL;DR

```bash
# 1. Start MongoDB
brew services start mongodb-community

# 2. Configure environment
cat > .env << 'EOF'
MONGODB_URI=mongodb://localhost:27017/
MONGO_DB_NAME=ai_scientist
MONGO_COLLECTION=experiments
SLACK_VERIFICATION_TOKEN=
PORT=8000
EOF

# 3. Start the API server
source .venv/bin/activate
python ai_scientist/dashboard/slack_api.py

# 4. In another terminal, start ngrok
ngrok http 8000

# 5. Add slash command to Slack app with ngrok URL
# 6. Reinstall Slack app to workspace
# 7. Test in Slack: /research energy_guided_self_models
```

## Answering Your Questions

### 1. What does Slack send in the POST request?

Slack sends `application/x-www-form-urlencoded` data with these fields:

```python
{
    "token": "verification_token",      # Security token
    "team_id": "T123456",               # Workspace ID
    "team_domain": "yourworkspace",     # Workspace domain
    "channel_id": "C123456",            # Channel ID where command was run
    "channel_name": "general",          # Channel name
    "user_id": "U123456",               # User who ran the command
    "user_name": "jessica",             # Username
    "command": "/research",             # The slash command
    "text": "energy_guided_self_models attempt_id=1",  # Everything after the command
    "response_url": "https://hooks.slack.com/...",     # For delayed responses
    "trigger_id": "13345224609.738474920.808893..."    # For opening modals
}
```

**Example**: If you type in Slack:
```
/research energy_guided_self_models attempt_id=1 model_writeup=o3-mini
```

Slack sends:
- `command` = `/research`
- `text` = `energy_guided_self_models attempt_id=1 model_writeup=o3-mini`

The endpoint parses this `text` field to extract the idea name and parameters.

### 2. Do you need to reinstall the Slack app?

**YES** - You need to **reinstall the Slack app** after adding the slash command!

Here's why:
1. When you first create a Slack app, it doesn't have any slash commands
2. When you add a slash command, it's added to the app configuration
3. **But** installed instances of the app don't automatically get updated
4. You must **reinstall** to get the new slash command

**How to reinstall:**
1. In your Slack app settings, go to **"Install App"**
2. Click **"Reinstall App"** (or "Install to Workspace" if not installed yet)
3. Click **"Allow"** to authorize

**Note**: If you see "Install to Workspace" instead of "Reinstall", that means the app wasn't installed yet, so just click that.

### 3. Testing the endpoint

#### Test locally (before Slack):
```bash
# Terminal 1: Start server
source .venv/bin/activate
python ai_scientist/dashboard/slack_api.py

# Terminal 2: Run test suite
source .venv/bin/activate
python test_slack_endpoint.py
```

The test script simulates what Slack sends, so you can verify everything works before connecting to Slack.

#### Test with Slack:
Once you've:
- Started the server
- Set up ngrok
- Added the slash command
- **Reinstalled the app** ✓

Just type in any Slack channel:
```
/research energy_guided_self_models
```

## What Gets Stored in MongoDB

Each experiment is stored as a document:

```json
{
  "_id": "ObjectId(...)",
  "experiment_id": "65a1b2c3d4e5f6...",
  "idea_name": "energy_guided_self_models",
  "idea_path": "/path/to/idea.json",
  "created_at": "2025-10-16T12:00:00Z",
  "created_by_slack_user": "jessica",
  "created_by_slack_user_id": "U123456",
  "slack_channel": "ai-experiments",
  "slack_channel_id": "C123456",
  "slack_team_id": "T123456",
  "status": "running",
  "started_at": "2025-10-16T12:00:01Z",
  "parameters": {
    "attempt_id": 0,
    "model_writeup": "o1-preview-2024-09-12",
    "model_citation": "gpt-4o-2024-11-20",
    "writeup_type": "icbinb",
    "num_cite_rounds": 20
  },
  "command": "/research",
  "command_text": "energy_guided_self_models attempt_id=0"
}
```

## Quick MongoDB Commands

```bash
# Connect to MongoDB
mongosh

# Switch to database
use ai_scientist

# List all experiments
db.experiments.find().pretty()

# Count experiments
db.experiments.countDocuments()

# Find running experiments
db.experiments.find({status: "running"}).pretty()

# Find experiments by user
db.experiments.find({created_by_slack_user: "jessica"}).pretty()

# Get latest experiment
db.experiments.find().sort({created_at: -1}).limit(1).pretty()
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### List Experiments
```bash
# Get last 10 experiments
curl http://localhost:8000/experiments

# Filter by status
curl http://localhost:8000/experiments?status=running

# Filter by user
curl http://localhost:8000/experiments?user=jessica

# Limit results
curl http://localhost:8000/experiments?limit=5
```

### Get Specific Experiment
```bash
curl http://localhost:8000/experiments/<experiment_id>
```

## Troubleshooting

### Command doesn't appear in Slack
- Did you reinstall the app? ← **Most common issue!**
- Check the slash command is configured correctly
- Try typing `/` in Slack to see if `/research` appears in the autocomplete

### "dispatch_failed" error
- Your server isn't reachable from the internet
- Check ngrok is running: `ngrok http 8000`
- Update Request URL in Slack app settings with new ngrok URL
- ngrok URLs change each time you restart ngrok (unless you have a paid plan)

### Verification token error
- Get token from Slack app → Basic Information → App Credentials
- Add to `.env`: `SLACK_VERIFICATION_TOKEN=your_token`
- Restart server
- Or leave empty to disable verification (not recommended for production)

### "Idea not found"
- List ideas: `ls ai_scientist/ideas/`
- Use filename without extension: `energy_guided_self_models` not `energy_guided_self_models.json`

## Full Example Workflow

```bash
# 1. Start MongoDB (if not running)
brew services start mongodb-community

# 2. Terminal 1: Start API server
cd /Users/jessica/AEStudio/agi/AI-Scientist-v2
source .venv/bin/activate
python ai_scientist/dashboard/slack_api.py
# Server starts on http://localhost:8000

# 3. Terminal 2: Start ngrok
ngrok http 8000
# Note the URL: https://abc123.ngrok.io

# 4. Configure Slack app:
# - Go to https://api.slack.com/apps
# - Select your app
# - Go to "Slash Commands"
# - Click "Create New Command"
#   - Command: /research
#   - Request URL: https://abc123.ngrok.io/slack/research
#   - Description: Launch an AI research experiment
#   - Usage Hint: [idea_name] [attempt_id=0] [model=o1-preview]
# - Save
# - Go to "Install App"
# - Click "Reinstall App" ← IMPORTANT!
# - Authorize

# 5. Test in Slack:
/research energy_guided_self_models

# 6. Monitor:
# Terminal 3: Watch logs
tail -f /tmp/pipeline_energy_guided_self_models_attempt_0.log

# Terminal 4: Query MongoDB
mongosh
use ai_scientist
db.experiments.find().pretty()
```

## Next Steps

- See `SLACK_SETUP.md` for detailed setup instructions
- See `ENV_CONFIG.md` for environment variable configuration
- Run `python test_slack_endpoint.py` to test locally
- Consider setting up persistent ngrok URL (paid plan) for production
- Add webhook to send experiment completion notifications back to Slack

