#!/usr/bin/env python3
"""
Test Coverage Checker - Shows what's tested and what's missing.
Run this to see your testing health at a glance.
"""

import os
import sys
from pathlib import Path
from collections import defaultdict

def find_test_files(root_dir="."):
    """Find all test files in the project"""
    test_files = []
    tests_dir = Path(root_dir) / "tests"
    
    if tests_dir.exists():
        for test_file in tests_dir.rglob("test_*.py"):
            test_files.append(test_file)
    
    return test_files

def count_tests_in_file(file_path):
    """Count test functions in a file"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Count lines starting with "def test_" or "async def test_"
    test_count = content.count('\ndef test_') + content.count('\nasync def test_')
    return test_count

def check_critical_tests():
    """Check if critical tests exist"""
    critical_tests = {
        "Event Schema Validation": "tests/integration/test_event_schemas.py",
        "State Transitions": "tests/integration/test_state_transitions.py",
        "Event Ingestion": "tests/integration/test_event_ingestion.py",
        "Artifact Upload": "tests/integration/test_artifacts.py",
        "Pod Worker Events": "tests/unit/test_pod_worker_events.py",
    }
    
    results = {}
    for name, path in critical_tests.items():
        exists = os.path.exists(path)
        test_count = count_tests_in_file(path) if exists else 0
        results[name] = {
            "exists": exists,
            "count": test_count,
            "path": path
        }
    
    return results

def check_event_coverage():
    """Check which event types have tests"""
    # All event types pod worker can emit
    pod_events = {
        "ai.run.started",
        "ai.run.heartbeat",
        "ai.run.completed",
        "ai.run.failed",
        "ai.run.canceled",
        "ai.run.stage_started",
        "ai.run.stage_progress",
        "ai.run.stage_completed",
        "ai.artifact.registered",
        "ai.run.log",
        "ai.validation.auto_started",
        "ai.validation.auto_completed",
        "ai.paper.started",
        "ai.paper.generated"
    }
    
    # Check if tests exist for each
    tested_events = set()
    test_files = find_test_files()
    
    for test_file in test_files:
        with open(test_file, 'r') as f:
            content = f.read()
            for event in pod_events:
                if event in content:
                    tested_events.add(event)
    
    untested_events = pod_events - tested_events
    
    return {
        "total": len(pod_events),
        "tested": len(tested_events),
        "untested": untested_events
    }

def main():
    print("=" * 60)
    print("🧪 AI Scientist Test Coverage Report")
    print("=" * 60)
    print()
    
    # 1. Test file discovery
    test_files = find_test_files()
    total_tests = sum(count_tests_in_file(f) for f in test_files)
    
    print(f"📁 Test Files Found: {len(test_files)}")
    print(f"🧪 Total Test Cases: {total_tests}")
    print()
    
    # 2. Critical tests
    print("🎯 Critical Tests Status:")
    print("-" * 60)
    
    critical = check_critical_tests()
    for name, info in critical.items():
        status = "✅" if info["exists"] else "❌"
        count_str = f"({info['count']} tests)" if info["exists"] else "(missing)"
        print(f"{status} {name:30s} {count_str}")
        if not info["exists"]:
            print(f"   📝 Create: {info['path']}")
    
    print()
    
    # 3. Event coverage
    print("📨 Event Type Coverage:")
    print("-" * 60)
    
    event_coverage = check_event_coverage()
    coverage_pct = (event_coverage["tested"] / event_coverage["total"]) * 100
    
    print(f"Covered: {event_coverage['tested']}/{event_coverage['total']} ({coverage_pct:.0f}%)")
    
    if event_coverage["untested"]:
        print("\n❌ Untested event types:")
        for event in sorted(event_coverage["untested"]):
            print(f"   - {event}")
    else:
        print("✅ All event types have tests!")
    
    print()
    
    # 4. Test categories breakdown
    print("📊 Test Categories:")
    print("-" * 60)
    
    categories = defaultdict(int)
    for test_file in test_files:
        if "unit" in str(test_file):
            categories["Unit Tests"] += count_tests_in_file(test_file)
        elif "integration" in str(test_file):
            categories["Integration Tests"] += count_tests_in_file(test_file)
        elif "e2e" in str(test_file):
            categories["E2E Tests"] += count_tests_in_file(test_file)
        else:
            categories["Other Tests"] += count_tests_in_file(test_file)
    
    for category, count in sorted(categories.items()):
        print(f"{category:20s}: {count:3d} tests")
    
    print()
    
    # 5. Health score
    print("💯 Test Health Score:")
    print("-" * 60)
    
    critical_score = sum(1 for info in critical.values() if info["exists"] and info["count"] > 0) / len(critical) * 100
    event_score = coverage_pct
    volume_score = min(100, (total_tests / 50) * 100)  # Target: 50 tests
    
    overall_score = (critical_score * 0.5 + event_score * 0.3 + volume_score * 0.2)
    
    print(f"Critical Tests:  {critical_score:.0f}%")
    print(f"Event Coverage:  {event_score:.0f}%")
    print(f"Test Volume:     {volume_score:.0f}%")
    print()
    print(f"Overall Score:   {overall_score:.0f}%")
    
    if overall_score >= 80:
        print("🎉 Excellent! You can sleep well at night.")
    elif overall_score >= 60:
        print("😊 Good progress! Keep adding tests.")
    elif overall_score >= 40:
        print("⚠️  Fair coverage. Focus on critical tests.")
    else:
        print("🚨 Low coverage. Start with TESTING_QUICKSTART.md")
    
    print()
    
    # 6. Next steps
    print("📝 Next Steps:")
    print("-" * 60)
    
    if overall_score < 60:
        print("1. Read TESTING_QUICKSTART.md")
        print("2. Implement the 5 critical tests")
        print("3. Run: pytest tests/ -v")
    else:
        print("1. Add tests for untested event types")
        print("2. Increase test volume (target: 50+ tests)")
        print("3. Set up CI/CD to run tests automatically")
    
    print()
    print("Run 'pytest tests/ -v' to execute tests")
    print("Run 'pytest --cov=. --cov-report=html' for coverage report")
    print()

if __name__ == "__main__":
    main()

