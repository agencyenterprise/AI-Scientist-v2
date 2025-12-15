#!/usr/bin/env python3
"""
Diagnostic script to verify ChatGPT context flows correctly through the system.

Usage:
    python diagnose_chatgpt_context.py                     # Check latest hypothesis
    python diagnose_chatgpt_context.py <hypothesis_id>     # Check specific hypothesis
    python diagnose_chatgpt_context.py --simulate <id>     # Simulate what pod_worker would do
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient


def diagnose_hypothesis(hypothesis_id: str = None, simulate: bool = False):
    """Diagnose ChatGPT context flow for a hypothesis."""
    client = MongoClient(os.environ['MONGODB_URL'])
    db = client['ai-scientist']
    
    print("=" * 70)
    print("🔍 ChatGPT Context Flow Diagnostic")
    print("=" * 70 + "\n")
    
    # Find hypothesis
    if hypothesis_id:
        hyp = db.hypotheses.find_one({"_id": hypothesis_id})
        if not hyp:
            print(f"❌ Hypothesis not found: {hypothesis_id}")
            return False
    else:
        # Get latest with chatGptUrl
        hyp = db.hypotheses.find_one(
            {"chatGptUrl": {"$exists": True}},
            sort=[("createdAt", -1)]
        )
        if not hyp:
            print("❌ No hypothesis with chatGptUrl found")
            return False
    
    hyp_id = hyp["_id"]
    print(f"📋 HYPOTHESIS: {hyp_id}")
    print(f"   Title: {hyp.get('title', 'N/A')[:60]}...")
    print(f"   Created: {hyp.get('createdAt')}")
    print()
    
    # Check ChatGPT URL
    chatgpt_url = hyp.get("chatGptUrl")
    print("1️⃣ ChatGPT URL stored in MongoDB:")
    if chatgpt_url:
        print(f"   ✅ YES: {chatgpt_url[:70]}...")
    else:
        print("   ❌ NO - URL not saved!")
    print()
    
    # Check extraction status
    extraction_status = hyp.get("extractionStatus")
    print("2️⃣ Extraction Status:")
    print(f"   Status: {extraction_status or 'N/A'}")
    if extraction_status == "completed":
        print("   ✅ Extraction completed successfully")
    elif extraction_status == "extracting":
        print("   ⏳ Extraction still in progress...")
    elif extraction_status == "failed":
        print("   ❌ Extraction FAILED")
    else:
        print("   ⚠️ Unknown status")
    print()
    
    # Check extractedRawText
    extracted_text = hyp.get("extractedRawText", "")
    print("3️⃣ Extracted Raw Text in MongoDB:")
    if extracted_text:
        print(f"   ✅ YES: {len(extracted_text)} characters")
        print(f"   Preview: {extracted_text[:200]}...")
    else:
        print("   ❌ NO - Raw text not saved!")
        print("   This is the CRITICAL issue - experiments won't get ChatGPT context!")
    print()
    
    # Check ideaJson
    idea_json = hyp.get("ideaJson", {})
    print("4️⃣ ideaJson in MongoDB:")
    if idea_json:
        print(f"   ✅ Present with keys: {list(idea_json.keys())[:5]}...")
        if "ChatContext" in idea_json:
            print(f"   ℹ️ ChatContext already in ideaJson: {len(idea_json['ChatContext'])} chars")
        else:
            print("   ℹ️ ChatContext NOT in ideaJson (expected - added at runtime)")
    else:
        print("   ❌ NO ideaJson - experiment can't start!")
    print()
    
    # Find associated runs
    runs = list(db.runs.find({"hypothesisId": hyp_id}).sort("createdAt", -1).limit(3))
    print(f"5️⃣ Associated Runs: {len(runs)}")
    for run in runs:
        print(f"   Run {run['_id'][:8]}... status={run.get('status')} created={run.get('createdAt')}")
    print()
    
    # Simulate what pod_worker would do
    if simulate and extracted_text:
        print("=" * 70)
        print("🧪 SIMULATING pod_worker.py behavior")
        print("=" * 70 + "\n")
        
        # This is exactly what pod_worker does at lines 1280-1284
        chat_context = hyp.get("extractedRawText")
        if chat_context:
            print(f"📝 Found ChatGPT conversation context ({len(chat_context)} chars)")
            # Add to ideaJson so it flows through to the experiment agent
            simulated_idea_json = idea_json.copy()
            simulated_idea_json["ChatContext"] = chat_context
            
            print("\n✅ RESULT: ideaJson now has ChatContext!")
            print(f"   Total ideaJson keys: {list(simulated_idea_json.keys())}")
            print(f"   ChatContext length: {len(simulated_idea_json['ChatContext'])} chars")
            
            # Show what would be written to idea.json
            print("\n📄 This would be written to experiments/.../idea.json:")
            preview = json.dumps({
                k: (v[:100] + "..." if isinstance(v, str) and len(v) > 100 else v)
                for k, v in simulated_idea_json.items()
            }, indent=2)
            print(preview[:1000])
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 70)
    
    issues = []
    if not chatgpt_url:
        issues.append("❌ chatGptUrl not saved")
    if not extracted_text:
        issues.append("❌ extractedRawText not saved - CRITICAL!")
    if extraction_status == "failed":
        issues.append("❌ Extraction failed")
    if not idea_json:
        issues.append("❌ ideaJson missing")
    
    if issues:
        print("\n🚨 ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("\n✅ ALL CHECKS PASSED!")
        print("   ChatGPT context will flow to experiments correctly.")
    
    return len(issues) == 0


def main():
    args = sys.argv[1:]
    
    simulate = "--simulate" in args
    if simulate:
        args.remove("--simulate")
    
    hypothesis_id = args[0] if args else None
    
    success = diagnose_hypothesis(hypothesis_id, simulate)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

