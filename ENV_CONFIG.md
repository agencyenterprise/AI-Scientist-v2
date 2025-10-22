# Environment Configuration

Create a `.env` file in the project root with the following variables:

```env
# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017/
MONGO_DB_NAME=ai_scientist
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
MONGO_DB_NAME=ai_scientist
MONGO_COLLECTION=experiments
SLACK_VERIFICATION_TOKEN=
PORT=8000
EOF
```

