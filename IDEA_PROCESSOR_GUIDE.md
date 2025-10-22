# Idea Processor Testing Guide

## Overview

The `idea_processor.py` script polls MongoDB for new research ideas and processes them through the AI Scientist pipeline.

## Setup

1. **Install dependencies:**
   ```bash
   source .venv/bin/activate
   pip install pymongo
   ```

2. **Verify .env has MONGO_URL:**
   ```bash
   grep MONGO_URL .env
   ```

## Testing with Dry-Run Mode

Dry-run mode lets you test the entire flow without actually running the expensive AI Scientist commands.

### Step 1: Insert a Test Document

```bash
python insert_test_idea.py
```

This inserts a test idea into MongoDB with `seen: false`.

### Step 2: Run the Processor in Dry-Run Mode

```bash
python idea_processor.py --dry-run
```

**What happens:**
- ✅ Connects to MongoDB
- ✅ Polls for unseen documents every 60 seconds
- ✅ Creates the `.md` file in `ai_scientist/ideas/`
- ✅ **Prints** the commands it would run (without executing them)
- ✅ Shows what MongoDB updates it would make
- ✅ Continues polling in a loop

### Step 3: Review the Output

You should see output like:

```
Initialized IdeaProcessor
MongoDB collection: ideas
Ideas directory: /path/to/ai_scientist/ideas
Poll interval: 60s
Dry run mode: ENABLED
⚠️  DRY RUN MODE - Commands will be printed but not executed

============================================================
Starting polling loop...
============================================================

Found 1 new document(s)

############################################################
Processing document: <document_id>
Name: test_energy_guided_self_models
############################################################

✓ Created markdown file: ai_scientist/ideas/test_energy_guided_self_models.md

============================================================
Running: Ideation Phase
Command: python ai_scientist/perform_ideation_temp_free.py --workshop-file "ai_scientist/ideas/test_energy_guided_self_models.md" --model gpt-5 --max-num-generations 2 --num-reflections 5
Working directory: /path/to/workspace
============================================================

🔍 DRY RUN - Command would be executed with:
   Full command: source .venv/bin/activate && python ai_scientist/perform_ideation_temp_free.py ...
   Shell: /bin/zsh
   Timeout: 3600s (1 hour)

✓ [DRY RUN] Ideation Phase would be executed

============================================================
Running: Experiment Execution Phase
Command: python launch_scientist_bfts.py --load_ideas "ai_scientist/ideas/test_energy_guided_self_models.json" ...
Working directory: /path/to/workspace
============================================================

🔍 DRY RUN - Command would be executed with:
   Full command: source .venv/bin/activate && python launch_scientist_bfts.py ...
   Shell: /bin/zsh
   Timeout: 3600s (1 hour)

✓ [DRY RUN] Experiment Execution Phase would be executed

✓ Successfully completed processing for test_energy_guided_self_models

🔍 [DRY RUN] Would update document <id> with:
   seen: True
   errored: False
   completed: True
   processed_at: 2025-10-15 12:34:56.789000

[2025-10-15 12:35:00] No new documents found
```

### Step 4: Stop the Processor

Press `Ctrl+C` to stop the polling loop gracefully.

## Running in Production Mode

Once you've verified everything works with `--dry-run`, run it for real:

```bash
python idea_processor.py
```

This will:
1. Actually execute the AI Scientist commands
2. Mark documents as processed in MongoDB
3. Capture error traces if anything fails

## Command-Line Options

```bash
python idea_processor.py --help
```

**Options:**
- `--dry-run` - Print commands without executing them (testing mode)
- `--poll-interval SECONDS` - How often to check MongoDB (default: 60)
- `--collection NAME` - MongoDB collection name (default: 'ideas')

**Examples:**

```bash
# Test mode with faster polling
python idea_processor.py --dry-run --poll-interval 10

# Production with custom collection
python idea_processor.py --collection research_ideas

# Test with different collection and faster polling
python idea_processor.py --dry-run --poll-interval 5 --collection test_ideas
```

## MongoDB Document Schema

**Input (what you insert):**
```json
{
  "name": "my_research_idea",
  "content": "# Title: My Idea\n\n## Abstract\n\n...",
  "seen": false
}
```

**After Processing (what gets added):**
```json
{
  "name": "my_research_idea",
  "content": "...",
  "seen": true,
  "completed": true,       // or errored: true if failed
  "processed_at": "2025-10-15T12:34:56.789Z",
  
  // On error:
  "errored": true,
  "error_message": "Ideation phase failed",
  "ideation_trace": "Full error output...",  // or runtime_trace for experiment errors
}
```

## Troubleshooting

**"MONGO_URL environment variable not set"**
- Check your `.env` file has `MONGO_URL=mongodb://...`

**"Import pymongo could not be resolved"**
- Run: `source .venv/bin/activate && pip install pymongo`

**No documents found**
- Make sure you inserted a test document with `seen: false`
- Check you're using the correct collection name

**Markdown file not created**
- Check the `ai_scientist/ideas/` directory exists
- Verify the `content` field in your MongoDB document has the markdown text

