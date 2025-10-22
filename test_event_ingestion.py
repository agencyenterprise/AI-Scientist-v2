import requests
import json
from datetime import datetime
from ulid import ULID

CONTROL_PLANE_URL = "https://ai-scientist-v2-production.up.railway.app"


def test_single_event():
    print("\n" + "="*60)
    print("Testing single event ingestion")
    print("="*60 + "\n")
    
    event = {
        "specversion": "1.0",
        "id": str(ULID()),
        "source": "test://local",
        "type": "ai.run.heartbeat",
        "subject": "run/test-run-12345",
        "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datacontenttype": "application/json",
        "data": {
            "run_id": "test-run-12345",
            "gpu_util": 0.75,
            "mem_gb": 32.1,
            "temp_c": 61.5
        },
        "extensions": {
            "seq": 1
        }
    }
    
    print(f"Sending event: {event['type']}")
    print(f"Event ID: {event['id']}\n")
    
    response = requests.post(
        f"{CONTROL_PLANE_URL}/api/ingest/event",
        json=event,
        headers={"Content-Type": "application/cloudevents+json"},
        timeout=10
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    
    if response.status_code == 201:
        print("✅ Single event test PASSED")
    else:
        print("❌ Single event test FAILED")
    
    return response.status_code == 201


def test_batch_events():
    print("\n" + "="*60)
    print("Testing batch event ingestion (NDJSON)")
    print("="*60 + "\n")
    
    events = []
    run_id = f"test-run-{ULID()}"
    
    for i in range(1, 4):
        event = {
            "specversion": "1.0",
            "id": str(ULID()),
            "source": "test://local",
            "type": "ai.run.stage_progress",
            "subject": f"run/{run_id}",
            "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "datacontenttype": "application/json",
            "data": {
                "run_id": run_id,
                "stage": "Stage_1",
                "progress": i * 0.25,
                "eta_s": 300 - (i * 100)
            },
            "extensions": {
                "seq": i
            }
        }
        events.append(event)
    
    ndjson = "\n".join(json.dumps(e) for e in events)
    
    print(f"Sending {len(events)} events for run: {run_id}\n")
    
    response = requests.post(
        f"{CONTROL_PLANE_URL}/api/ingest/events",
        data=ndjson,
        headers={"Content-Type": "application/x-ndjson"},
        timeout=10
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    
    if response.status_code == 202:
        result = response.json()
        if result.get("accepted") == len(events):
            print("✅ Batch event test PASSED")
            return True
        else:
            print(f"⚠ Partial success: {result.get('accepted')}/{len(events)} accepted")
            return False
    else:
        print("❌ Batch event test FAILED")
        return False


def test_duplicate_event():
    print("\n" + "="*60)
    print("Testing duplicate event detection")
    print("="*60 + "\n")
    
    event_id = str(ULID())
    
    event = {
        "specversion": "1.0",
        "id": event_id,
        "source": "test://local",
        "type": "ai.run.heartbeat",
        "subject": "run/test-run-duplicate",
        "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datacontenttype": "application/json",
        "data": {
            "run_id": "test-run-duplicate",
            "gpu_util": 0.5
        },
        "extensions": {
            "seq": 1
        }
    }
    
    print(f"Sending event first time (ID: {event_id})...")
    response1 = requests.post(
        f"{CONTROL_PLANE_URL}/api/ingest/event",
        json=event,
        headers={"Content-Type": "application/cloudevents+json"},
        timeout=10
    )
    
    print(f"Status: {response1.status_code}")
    print(f"Response: {json.dumps(response1.json(), indent=2)}\n")
    
    print(f"Sending SAME event again (should be ignored)...")
    response2 = requests.post(
        f"{CONTROL_PLANE_URL}/api/ingest/event",
        json=event,
        headers={"Content-Type": "application/cloudevents+json"},
        timeout=10
    )
    
    print(f"Status: {response2.status_code}")
    print(f"Response: {json.dumps(response2.json(), indent=2)}\n")
    
    if response2.status_code == 201 and response2.json().get("status") == "duplicate":
        print("✅ Duplicate detection test PASSED")
        return True
    else:
        print("❌ Duplicate detection test FAILED")
        return False


def test_invalid_event():
    print("\n" + "="*60)
    print("Testing invalid event rejection")
    print("="*60 + "\n")
    
    invalid_event = {
        "specversion": "1.0",
        "id": str(ULID()),
        "type": "ai.run.heartbeat",
    }
    
    print(f"Sending invalid event (missing required fields)...\n")
    
    response = requests.post(
        f"{CONTROL_PLANE_URL}/api/ingest/event",
        json=invalid_event,
        headers={"Content-Type": "application/cloudevents+json"},
        timeout=10
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    
    if response.status_code == 422:
        print("✅ Invalid event rejection test PASSED")
        return True
    else:
        print("❌ Invalid event rejection test FAILED")
        return False


def main():
    print("\n" + "="*60)
    print("AI Scientist Event Ingestion Tests")
    print(f"Control Plane: {CONTROL_PLANE_URL}")
    print("="*60)
    
    results = []
    
    try:
        results.append(("Single Event", test_single_event()))
        results.append(("Batch Events", test_batch_events()))
        results.append(("Duplicate Detection", test_duplicate_event()))
        results.append(("Invalid Event Rejection", test_invalid_event()))
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Could not connect to {CONTROL_PLANE_URL}")
        print("Make sure the control plane is running and accessible.")
        return
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60 + "\n")
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name:30s} {status}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED")
    else:
        print("⚠ SOME TESTS FAILED")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()

