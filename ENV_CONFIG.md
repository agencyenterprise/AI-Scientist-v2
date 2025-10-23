# Environment Configuration

## ⚠️ IMPORTANT: Database Naming Convention

**Always use `ai-scientist` (with hyphen) as the MongoDB database name.**

The orchestrator frontend uses the `MONGODB_DB` environment variable, and all backend services (pod_worker.py, idea_processor.py) are configured to use `ai-scientist` with a hyphen.

---

Create a `.env` file in the project root with the following variables:

```env
# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB=ai-scientist
MONGO_COLLECTION=experiments

# Slack Configuration (optional but recommended)
# Get this from your Slack App's "Basic Information" page
SLACK_VERIFICATION_TOKEN=your_verification_token_here

# Server Configuration
PORT=8000

# OpenAI API Key (if not already set)
# OPENAI_API_KEY=your_openai_api_key_here

# Anthropic API Key (if not already set)
# ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Copy this to create your `.env` file:
```bash
cat > .env << 'EOF'
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB=ai-scientist
MONGO_COLLECTION=experiments
SLACK_VERIFICATION_TOKEN=
PORT=8000
EOF
```

