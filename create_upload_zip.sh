#!/bin/bash
# Create a zip file for RunPod upload (excluding unnecessary files)

OUTPUT_FILE="ai-scientist-runpod.zip"

echo "Creating RunPod upload package..."
echo "Excluding: .venv, .git, __pycache__, experiments, etc."

zip -r "$OUTPUT_FILE" . \
  -x "*.venv/*" \
  -x "*.git/*" \
  -x "*__pycache__/*" \
  -x "*.pyc" \
  -x "*/.DS_Store" \
  -x "*/experiments/*" \
  -x "*.pkl" \
  -x "*.log" \
  -x "*/node_modules/*" \
  -x "*/.pytest_cache/*" \
  -x "*/.mypy_cache/*"

SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
echo ""
echo "✅ Created: $OUTPUT_FILE ($SIZE)"
echo ""
echo "This file is ready to upload to RunPod!"
echo "After uploading, run: bash init_runpod.sh"

