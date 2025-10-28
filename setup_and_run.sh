#!/bin/bash
set -euo pipefail

echo "========================================"
echo "🚀 AI Scientist v2 - RunPod Setup"
echo "========================================"
echo ""

# =============================================================================
# Step 1: Install Git and SSH if not present
# =============================================================================
echo "Step 1: Ensuring git and SSH client are installed..."
if ! command -v git >/dev/null 2>&1; then
  echo "  Installing git and openssh-client..."
  sudo apt-get update -y && sudo apt-get install -y git openssh-client
else
  echo "  ✓ git already installed"
fi

# =============================================================================
# Step 2: Configure SSH for GitHub
# =============================================================================
echo ""
echo "Step 2: Configuring SSH for GitHub..."

mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Add GitHub to known hosts
if ! grep -q "github.com" ~/.ssh/known_hosts 2>/dev/null; then
  echo "  Adding GitHub to known hosts..."
  ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null
  chmod 644 ~/.ssh/known_hosts
else
  echo "  ✓ GitHub already in known hosts"
fi

# Decode and save SSH key
: "${GIT_SSH_KEY_AI_SCIENTIST_V2_B64:?ERROR: GIT_SSH_KEY_AI_SCIENTIST_V2_B64 environment variable not set}"
echo "  Decoding SSH deploy key..."
echo "$GIT_SSH_KEY_AI_SCIENTIST_V2_B64" | base64 -d > ~/.ssh/id_deploy_AI_Scientist_v2
chmod 600 ~/.ssh/id_deploy_AI_Scientist_v2

# Configure SSH config
if ! grep -q "Host github.com-AI-Scientist-v2" ~/.ssh/config 2>/dev/null; then
  echo "  Writing SSH config..."
  cat >> ~/.ssh/config <<'EOF'
Host github.com-AI-Scientist-v2
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_deploy_AI_Scientist_v2
  IdentitiesOnly yes
EOF
  chmod 600 ~/.ssh/config
else
  echo "  ✓ SSH config already exists"
fi

# Set git config
git config --global user.name "RunPod Worker" 2>/dev/null || true
git config --global user.email "runpod@local" 2>/dev/null || true

echo "  ✓ SSH configured"

# =============================================================================
# Step 3: Test SSH connection
# =============================================================================
echo ""
echo "Step 3: Testing SSH connection to GitHub..."
# Redirect stdin to prevent SSH from consuming the piped script
if ssh -T git@github.com-AI-Scientist-v2 </dev/null 2>&1 | grep -q "successfully authenticated"; then
  echo "  ✅ SSH authentication successful!"
else
  echo "  ⚠️  SSH test gave unexpected output, but continuing..."
fi

# =============================================================================
# Step 4: Clone or update repository
# =============================================================================
echo ""
echo "Step 4: Setting up AI-Scientist-v2 repository..."

REPO_DIR="/workspace/AI-Scientist-v2"
REPO_URL="git@github.com-AI-Scientist-v2:agencyenterprise/AI-Scientist-v2.git"
TARGET_BRANCH="feat/additions"

if [ -d "$REPO_DIR" ]; then
  echo "  Repository directory exists, updating..."
  cd "$REPO_DIR"
  
  # Fetch latest changes
  echo "  Fetching latest changes..."
  git fetch origin
  
  # Check if we're on the right branch
  CURRENT_BRANCH=$(git branch --show-current)
  if [ "$CURRENT_BRANCH" != "$TARGET_BRANCH" ]; then
    echo "  Switching to branch $TARGET_BRANCH..."
    git checkout "$TARGET_BRANCH"
  fi
  
  # Pull latest changes
  echo "  Pulling latest changes..."
  git pull origin "$TARGET_BRANCH"
  
  echo "  ✓ Repository updated"
else
  echo "  Cloning repository..."
  cd /workspace
  git clone "$REPO_URL"
  cd "$REPO_DIR"
  
  echo "  Checking out branch $TARGET_BRANCH..."
  git fetch origin "$TARGET_BRANCH"
  git checkout "$TARGET_BRANCH"
  
  echo "  ✓ Repository cloned"
fi

# =============================================================================
# Step 5: Run init_runpod.sh
# =============================================================================
echo ""
echo "Step 5: Running RunPod initialization script..."
echo "  (This will install Anaconda, Python packages, PyTorch, and LaTeX)"
echo ""
echo "========================================"
echo ""

if [ -f "$REPO_DIR/init_runpod.sh" ]; then
  cd "$REPO_DIR"
  # Use exec to replace this shell with init_runpod.sh
  # This ensures pod_worker.py will become the top-level process
  exec bash init_runpod.sh
else
  echo "❌ ERROR: init_runpod.sh not found in $REPO_DIR"
  echo "   Repository contents:"
  ls -la "$REPO_DIR"
  exit 1
fi

