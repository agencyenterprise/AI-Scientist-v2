#!/bin/bash

echo "🤖 Starting AI Scientist Pod Worker"
echo ""
echo "Make sure you have set the following environment variables:"
echo "  - MONGODB_URL"
echo "  - CONTROL_PLANE_URL (optional, defaults to production)"
echo "  - OPENAI_API_KEY"
echo "  - ANTHROPIC_API_KEY (optional)"
echo ""

if [ -z "$MONGODB_URL" ]; then
    echo "❌ MONGODB_URL not set. Please set it first:"
    echo "   export MONGODB_URL='mongodb://...'"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠ OPENAI_API_KEY not set. This may cause issues."
fi

source ~/.bashrc
conda activate ai_scientist 2>/dev/null || source .venv/bin/activate 2>/dev/null

python pod_worker.py

