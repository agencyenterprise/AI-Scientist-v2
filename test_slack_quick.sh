#!/bin/bash
# Quick test script for Slack endpoint

echo "Testing Slack /research endpoint..."
echo ""

# Test the slash command endpoint
curl -X POST http://localhost:8000/slack/research \
  -d "token=test_token" \
  -d "team_id=T123456" \
  -d "team_domain=testworkspace" \
  -d "channel_id=C123456" \
  -d "channel_name=ai-experiments" \
  -d "user_id=U123456" \
  -d "user_name=jessica" \
  -d "command=/research" \
  -d "text=energy_guided_self_models attempt_id=0" \
  -d "response_url=https://hooks.slack.com/test" \
  -d "trigger_id=12345" \
  | jq .

echo ""
echo "Now check experiments:"
curl http://localhost:8000/experiments | jq .



