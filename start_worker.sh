#!/bin/bash

echo "🤖 Starting AI Scientist Pod Worker"
echo ""

# Source shell profile to get conda/env vars
if [ -f "$HOME/.bashrc" ]; then
    # shellcheck source=/dev/null
    source "$HOME/.bashrc"
elif [ -f "$HOME/.zshrc" ]; then
    # shellcheck source=/dev/null
    source "$HOME/.zshrc"
fi

# Verify required environment variables
if [ -z "$MONGODB_URL" ]; then
    echo "❌ MONGODB_URL not set."
    echo ""
    echo "If you just ran init_runpod.sh, try:"
    echo "  source ~/.bashrc"
    echo "  bash start_worker.sh"
    echo ""
    echo "Or manually set:"
    echo "  export MONGODB_URL='mongodb://...'"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  OPENAI_API_KEY not set. The worker may fail."
    echo ""
fi

echo "✓ Environment ready"
echo ""
echo "Press Ctrl+C to stop the worker gracefully."
echo ""

python pod_worker.py "$@"
