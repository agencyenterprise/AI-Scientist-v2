#!/usr/bin/env python3
"""
Test script for the Slack endpoint.
Simulates a Slack slash command request.
"""
import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint."""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.status_code == 200

def test_slash_command(idea_name="energy_guided_self_models", attempt_id=0):
    """Test the /research slash command."""
    print(f"Testing /research slash command with idea: {idea_name}...")
    
    # This simulates what Slack sends when a user types:
    # /research energy_guided_self_models attempt_id=0 model_writeup=o1-preview
    
    payload = {
        "token": "test_verification_token",  # Set SLACK_VERIFICATION_TOKEN env var to match
        "team_id": "T123456",
        "team_domain": "testworkspace",
        "channel_id": "C123456",
        "channel_name": "ai-experiments",
        "user_id": "U123456",
        "user_name": "jessica",
        "command": "/research",
        "text": f"{idea_name} attempt_id={attempt_id} model_writeup=o1-preview-2024-09-12",
        "response_url": "https://hooks.slack.com/commands/1234/5678",
        "trigger_id": "13345224609.738474920.8088930838d88f008e0"
    }
    
    response = requests.post(f"{BASE_URL}/slack/research", data=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.status_code == 200

def test_list_experiments():
    """Test listing experiments."""
    print("Testing list experiments endpoint...")
    response = requests.get(f"{BASE_URL}/experiments?limit=5")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.status_code == 200

def test_invalid_idea():
    """Test with an idea that doesn't exist."""
    print("Testing with invalid idea name...")
    
    payload = {
        "token": "test_verification_token",
        "team_id": "T123456",
        "team_domain": "testworkspace",
        "channel_id": "C123456",
        "channel_name": "ai-experiments",
        "user_id": "U123456",
        "user_name": "jessica",
        "command": "/research",
        "text": "nonexistent_idea attempt_id=0",
        "response_url": "https://hooks.slack.com/commands/1234/5678",
        "trigger_id": "13345224609.738474920.8088930838d88f008e0"
    }
    
    response = requests.post(f"{BASE_URL}/slack/research", data=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.status_code == 200  # Should still return 200 but with error message

def test_empty_command():
    """Test with empty command text."""
    print("Testing with empty command text...")
    
    payload = {
        "token": "test_verification_token",
        "team_id": "T123456",
        "team_domain": "testworkspace",
        "channel_id": "C123456",
        "channel_name": "ai-experiments",
        "user_id": "U123456",
        "user_name": "jessica",
        "command": "/research",
        "text": "",
        "response_url": "https://hooks.slack.com/commands/1234/5678",
        "trigger_id": "13345224609.738474920.8088930838d88f008e0"
    }
    
    response = requests.post(f"{BASE_URL}/slack/research", data=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.status_code == 200

if __name__ == "__main__":
    print("=" * 60)
    print("Slack Endpoint Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        ("Health Check", test_health),
        ("Empty Command", test_empty_command),
        ("Invalid Idea", test_invalid_idea),
        ("Valid Research Command", lambda: test_slash_command("energy_guided_self_models", 0)),
        ("List Experiments", test_list_experiments),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, "✓ PASSED" if passed else "✗ FAILED"))
        except Exception as e:
            results.append((name, f"✗ ERROR: {str(e)}"))
        print("-" * 60)
        print()
    
    print("=" * 60)
    print("Test Results:")
    print("=" * 60)
    for name, result in results:
        print(f"{result:15} | {name}")
    print("=" * 60)

