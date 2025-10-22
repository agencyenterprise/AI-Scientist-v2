# MongoDB Testing & Cleanup Guide

## 🧪 Testing MongoDB Event Storage

### Test Script: `test_mongodb_events.py`

**What it tests:**
1. ✅ Events are stored in MongoDB `events` collection
2. ✅ Events are tracked in `events_seen` for deduplication
3. ✅ Duplicate events are ignored
4. ✅ Stage events create `stages` documents
5. ✅ Events trigger run status transitions

### Usage

```bash
# Make sure MONGODB_URL is set
export MONGODB_URL="mongodb+srv://user:pass@cluster.mongodb.net/ai_scientist"

# Run all tests
python test_mongodb_events.py
```

### Expected Output

```
============================================================
MongoDB Event Storage Tests
Control Plane: https://ai-scientist-v2-production.up.railway.app
============================================================

✓ Connected to MongoDB

============================================================
Test 1: Verify Event Stored in MongoDB
============================================================

Sending test event...
  Event ID: 01JDNW7K1E4VNH15Q7S6PTB9QY
  Run ID: 01JDNW3A21Q0X9MBYF4F1A9B3D
  Type: ai.run.heartbeat

Response: 201 - {'event_id': '01JDNW7K1E4VNH15Q7S6PTB9QY'}

✅ Event found in MongoDB!

Event document:
  _id: 01JDNW7K1E4VNH15Q7S6PTB9QY
  runId: 01JDNW3A21Q0X9MBYF4F1A9B3D
  type: ai.run.heartbeat
  source: test://mongodb-test
  timestamp: 2025-10-22 19:17:45
  seq: 1
  data: {'run_id': '01JDNW3A21Q0X9MBYF4F1A9B3D', 'gpu_util': 0.75}

...

============================================================
Test Summary
============================================================

Event Stored in MongoDB        ✅ PASSED
Event Deduplication            ✅ PASSED
Stage Creation                 ✅ PASSED
Run Status Transitions         ✅ PASSED

============================================================
🎉 ALL TESTS PASSED

Events are correctly stored in MongoDB!
============================================================
```

### What Gets Verified

**Test 1: Event Storage**
- Event inserted into `events` collection
- Correct fields (`_id`, `runId`, `type`, `source`, `timestamp`, `seq`, `data`)
- Event ID is the ULID sent

**Test 2: Deduplication**
- First event stored in `events_seen` collection
- Second event with same ID returns "duplicate" status
- No duplicate document created in `events`

**Test 3: Stage Creation**
- `ai.run.stage_started` event creates document in `stages` collection
- Stage document has correct `runId`, `name`, `status`, `progress`
- Stage ID matches pattern `{runId}-{stage}`

**Test 4: Status Transitions**
- Run created with `status: QUEUED`
- `ai.run.started` event transitions to `status: RUNNING`
- Pod info populated from event data
- `lastEventSeq` updated

---

## 🧹 Cleaning MongoDB

### Cleanup Script: `cleanup_mongodb.py`

**Safe operations for different scenarios:**

### 1. Check Database Stats (No Changes)

```bash
python cleanup_mongodb.py --stats
```

Shows document counts for all collections:
```
Current Database Statistics
============================================================

runs                      15 documents
hypotheses                10 documents
stages                    45 documents
validations               12 documents
artifacts                 23 documents
events                   234 documents
events_seen              234 documents
------------------------------------------------------------
TOTAL                    573 documents
```

### 2. Clean Failed/Canceled Runs Only (Safe)

```bash
python cleanup_mongodb.py --failed
```

**What it does:**
- Finds runs with `status: FAILED` or `status: CANCELED`
- Deletes those runs + their stages, validations, artifacts, events
- **Keeps:** Successful runs, queued runs, running runs

**Use case:** Clean up failed experiments to start fresh

### 3. Clean Test Data (Safe)

```bash
python cleanup_mongodb.py --test
```

**What it does:**
- Deletes events with `source` matching `test://` pattern
- Deletes `events_seen` records with IDs starting with `test-`

**Use case:** Clean up test events from `test_mongodb_events.py` or `test_event_ingestion.py`

### 4. Clean Specific Run (Surgical)

```bash
python cleanup_mongodb.py --run <run_id>
```

**What it does:**
- Deletes one specific run + all its related data
- Shows what will be deleted before proceeding

**Use case:** Remove a specific problematic run

### 5. Clean Old Events (Maintenance)

```bash
# Clean events older than 7 days (default)
python cleanup_mongodb.py --old-events

# Clean events older than 30 days
python cleanup_mongodb.py --old-events --days 30
```

**What it does:**
- Deletes events from `events` collection older than N days
- Deletes corresponding `events_seen` records
- **Keeps:** Runs, stages, validations, artifacts (only cleans event logs)

**Use case:** Regular maintenance to prevent event table bloat

### 6. Clean Everything (DANGEROUS - Fresh Start)

```bash
# Clean all non-seed data
python cleanup_mongodb.py --all

# Clean EVERYTHING including seed data
python cleanup_mongodb.py --all --include-seed --yes
```

**What it does:**
- Deletes ALL documents from ALL collections
- By default excludes `seed: true` documents
- Use `--include-seed` to delete seed data too

**Use case:** Complete fresh start (e.g., switching environments)

---

## 🔒 Safety Features

### Confirmation Prompts

All destructive operations require confirmation:

```bash
$ python cleanup_mongodb.py --failed

Current Database Statistics
============================================================
runs                      15 documents
hypotheses                10 documents
...

⚠️  WARNING: This will delete data from MongoDB!

Are you sure you want to continue? (yes/no): _
```

Skip prompt with `--yes` flag (use in scripts only):

```bash
python cleanup_mongodb.py --failed --yes
```

### Seed Data Protection

By default, documents with `seed: true` are preserved:

```javascript
// These won't be deleted by --all unless you use --include-seed
{
  "_id": "...",
  "title": "Example Hypothesis",
  "seed": true  // ← Protected
}
```

### Before & After Stats

Script shows database state before and after cleanup:

```
Current Database Statistics (BEFORE)
============================================================
runs                      15 documents
...

[... cleaning ...]

Current Database Statistics (AFTER)
============================================================
runs                       5 documents  // ← 10 deleted
...
```

---

## 📋 Common Workflows

### Starting Fresh Experiments

```bash
# 1. Check what you have
python cleanup_mongodb.py --stats

# 2. Clean failed runs
python cleanup_mongodb.py --failed

# 3. Verify cleanup
python cleanup_mongodb.py --stats

# 4. Create new hypotheses via frontend
```

### After Running Tests

```bash
# Clean up test data
python cleanup_mongodb.py --test

# Or clean specific test run
python cleanup_mongodb.py --run <test_run_id>
```

### Weekly Maintenance

```bash
# Clean old event logs (keep last 7 days)
python cleanup_mongodb.py --old-events --days 7 --yes

# Can be added to cron:
# 0 2 * * 0 cd /path && python cleanup_mongodb.py --old-events --yes
```

### Complete Reset (New Environment)

```bash
# Nuclear option - clean everything
python cleanup_mongodb.py --all --yes

# Then re-seed if needed
cd orchestrator/apps/web
npm run seed
```

---

## 🧪 Integration with Testing

### Test Workflow

```bash
# 1. Clean before testing
python cleanup_mongodb.py --test --yes

# 2. Run backend tests
cd orchestrator/apps/web
npm test

# 3. Run integration tests
cd ../../..
python test_event_ingestion.py

# 4. Test MongoDB storage
python test_mongodb_events.py

# 5. Clean up test data
python cleanup_mongodb.py --test --yes
```

### Automated Testing Script

```bash
#!/bin/bash
# test_all.sh

set -e

echo "Cleaning test data..."
python cleanup_mongodb.py --test --yes

echo "Running unit tests..."
cd orchestrator/apps/web && npm test && cd ../../..

echo "Running integration tests..."
python test_event_ingestion.py

echo "Testing MongoDB storage..."
python test_mongodb_events.py

echo "Cleaning up..."
python cleanup_mongodb.py --test --yes

echo "✅ All tests passed!"
```

---

## 🔍 Troubleshooting

### Events Not Appearing in MongoDB

```bash
# 1. Check if events were sent
python test_mongodb_events.py

# 2. Check MongoDB connection
python manage_runs.py stats

# 3. Check backend logs (Railway)
# Look for errors in event processing

# 4. Verify event schema
# Check that events match CloudEvents spec
```

### Database Growing Too Large

```bash
# 1. Check what's taking space
python cleanup_mongodb.py --stats

# 2. Clean old events
python cleanup_mongodb.py --old-events --days 7

# 3. Clean failed runs
python cleanup_mongodb.py --failed

# 4. Consider adding TTL index to events collection
# (Already exists for events_seen - 7 days)
```

### Duplicate Events

```bash
# 1. Check events_seen collection
python test_mongodb_events.py  # Test 2 specifically

# 2. Clean and retry
python cleanup_mongodb.py --test
python test_event_ingestion.py
```

---

## 📊 MongoDB Collections Overview

| Collection | Purpose | Cleanup Strategy |
|------------|---------|------------------|
| `runs` | Run metadata | Keep successful, delete failed |
| `hypotheses` | Research ideas | Rarely delete (history) |
| `stages` | Stage progress | Delete with parent run |
| `validations` | Auto/human reviews | Delete with parent run |
| `artifacts` | File references | Delete with parent run |
| `events` | Event log | Delete old events (>7 days) |
| `events_seen` | Deduplication | Auto-cleaned by TTL (7 days) |

---

## 🎯 Best Practices

1. **Before Fresh Start:**
   ```bash
   python cleanup_mongodb.py --failed  # Clean failures
   python cleanup_mongodb.py --test    # Clean test data
   ```

2. **Regular Maintenance:**
   ```bash
   # Weekly cron job
   python cleanup_mongodb.py --old-events --days 7 --yes
   ```

3. **After Testing:**
   ```bash
   python cleanup_mongodb.py --test --yes
   ```

4. **Before Demo:**
   ```bash
   python cleanup_mongodb.py --stats  # Check state
   python cleanup_mongodb.py --failed # Clean failures
   ```

5. **Production:**
   - Never use `--all --include-seed` in production
   - Always check `--stats` before cleanup
   - Use `--failed` instead of `--all` for safety
   - Keep event logs for at least 7 days

---

## 📝 Quick Reference

```bash
# Stats only (safe)
python cleanup_mongodb.py --stats

# Clean failed runs
python cleanup_mongodb.py --failed

# Clean test data
python cleanup_mongodb.py --test

# Clean specific run
python cleanup_mongodb.py --run <run_id>

# Clean old events
python cleanup_mongodb.py --old-events --days 7

# Fresh start (careful!)
python cleanup_mongodb.py --all

# Test MongoDB storage
python test_mongodb_events.py

# Test event ingestion
python test_event_ingestion.py
```

---

**Need help?** Run with `--help`:
```bash
python cleanup_mongodb.py --help
python test_mongodb_events.py --help  # (coming soon)
```

