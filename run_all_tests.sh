#!/bin/bash
set -e

echo "="*60
echo "Running Complete Test Suite"
echo "="*60

# Activate environment
source .venv/bin/activate || source ~/anaconda3/bin/activate ai_scientist

# Load environment variables
export $(cat .env | grep -v '^#' | xargs) 2>/dev/null || true

echo ""
echo "Step 1: Pre-deployment validation"
echo "-"*60
python test_observability.py
echo "✓ Pre-deployment checks passed"

echo ""
echo "Step 2: Unit tests"
echo "-"*60
pytest tests/unit/test_pod_worker.py -v --tb=short
echo "✓ Unit tests passed"

echo ""
echo "Step 3: Integration tests"
echo "-"*60
pytest tests/integration/test_complete_experiment_flow.py -v --tb=short
echo "✓ Integration tests passed"

echo ""
echo "Step 4: End-to-end pod worker tests"
echo "-"*60
pytest tests/integration/test_pod_worker_e2e.py -v --tb=short
echo "✓ E2E tests passed"

echo ""
echo "="*60
echo "✅ ALL TESTS PASSED"
echo "="*60
echo ""
echo "System is ready for deployment!"
echo ""
echo "Next steps:"
echo "  1. Deploy frontend: cd orchestrator/apps/web && pnpm build"
echo "  2. Deploy to pod: git pull origin feat/additions"
echo "  3. Start worker: python pod_worker.py"
echo "  4. Create test hypothesis and verify observability"
echo ""

