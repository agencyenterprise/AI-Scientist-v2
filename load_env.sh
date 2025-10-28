#!/bin/bash
# Load environment variables from .env file

if [ ! -f .env ]; then
    echo "❌ .env file not found in current directory"
    echo "   Please create a .env file first"
    exit 1
fi

echo "📥 Loading environment variables from .env..."

# Export each line that matches KEY=value pattern
while IFS= read -r line; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    
    # Only process lines that match KEY=value pattern
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
        # Remove quotes if present
        cleaned_line=$(echo "$line" | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\(.*\)'$/\1/")
        export "$cleaned_line"
        # Get just the key name for display
        key=$(echo "$line" | cut -d= -f1)
        echo "  ✓ Loaded: $key"
    fi
done < .env

echo ""
echo "✅ Environment variables loaded!"
echo ""
echo "Now you can run: python pod_worker.py"

