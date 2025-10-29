#!/bin/bash
# Script to manually copy critical files to pod via copy-paste

echo "Creating deployment package..."

# Create a single Python script that contains all file updates
cat > /tmp/pod_deploy.py << 'DEPLOY_SCRIPT'
#!/usr/bin/env python3
"""
Run this script on the pod to update all critical files.
Paste this entire file into the pod terminal, then run: python3 pod_deploy.py
"""

import os
from pathlib import Path

# Map of file paths to their contents
FILES = {}

DEPLOY_SCRIPT

# Add each file
for file in pod_worker.py experiment_monitor.py monitor_experiment.py ai_scientist/treesearch/perform_experiments_bfts_with_agentmanager.py idea_processor.py; do
    echo "files['$file'] = '''$(cat $file)'''" >> /tmp/pod_deploy.py
done

cat >> /tmp/pod_deploy.py << 'DEPLOY_FOOTER'

def deploy():
    print("Deploying files to pod...")
    for file_path, content in FILES.items():
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        print(f"✓ Updated {file_path}")
    print("\n✅ All files deployed!")
    print("\nNext: python pod_worker.py")

if __name__ == "__main__":
    deploy()
DEPLOY_FOOTER

echo "✓ Created /tmp/pod_deploy.py"
echo ""
echo "To deploy:"
echo "  1. Copy the contents of /tmp/pod_deploy.py"
echo "  2. Paste into pod terminal"
echo "  3. Run: python3 /tmp/pod_deploy.py"
echo ""

