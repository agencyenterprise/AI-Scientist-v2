import { NextRequest, NextResponse } from "next/server"
import { getDb } from "@/lib/db/mongo"
import { randomUUID } from "crypto"
import { spawn } from "child_process"
import path from "path"
import fs from "fs"

export const runtime = "nodejs"

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    
    const db = await getDb()
    const runsCollection = db.collection("runs")
    const eventsCollection = db.collection("events")
    
    const run = await runsCollection.findOne({ _id: id })
    
    if (!run) {
      return NextResponse.json(
        { error: "Run not found" },
        { status: 404 }
      )
    }
    
    const experimentRoot = process.env.EXPERIMENT_ROOT || "/workspace/AI-Scientist-v2 copy/experiments"
    
    const experimentDirs = fs.readdirSync(experimentRoot)
      .filter(dir => dir.includes(id))
      .sort()
    
    if (experimentDirs.length === 0) {
      return NextResponse.json(
        { error: "No experiment directory found for this run" },
        { status: 404 }
      )
    }
    
    // Use the MOST RECENT experiment directory for this run
    const experimentDir = path.join(experimentRoot, experimentDirs[experimentDirs.length - 1])
    
    // Emit starting event
    await eventsCollection.insertOne({
      id: randomUUID(),
      specversion: "1.0",
      source: "web/retry-writeup",
      type: "ai.run.paper.retry.started",
      subject: `run/${id}`,
      time: new Date().toISOString(),
      datacontenttype: "application/json",
      data: {
        message: "Paper generation retry started",
        experimentDir: experimentDirs[experimentDirs.length - 1]
      }
    })
    
    const pythonPath = process.env.PYTHON_PATH || "python"
    const scriptPath = process.env.AI_SCIENTIST_ROOT || "/workspace/AI-Scientist-v2 copy"
    
    // Create a wrapper script that emits events
    const wrapperScript = path.join("/tmp", `writeup_${id}.sh`)
    const wrapperContent = `#!/bin/bash
set -e

# Emit progress events via MongoDB
MONGO_URL="${process.env.MONGODB_URL}"
RUN_ID="${id}"

emit_event() {
  local event_type=$1
  local message=$2
  python3 << PYEOF
import os
from pymongo import MongoClient
from datetime import datetime
from uuid import uuid4

client = MongoClient(os.environ.get('MONGODB_URL'))
db = client['ai-scientist']
db.events.insert_one({
    'id': str(uuid4()),
    'specversion': '1.0',
    'source': 'writeup-retry',
    'type': '$event_type',
    'subject': 'run/$RUN_ID',
    'time': datetime.utcnow().isoformat() + 'Z',
    'datacontenttype': 'application/json',
    'data': {'message': '$message'}
})
PYEOF
}

cd "${scriptPath}"

emit_event "ai.run.log" "📊 Aggregating plots..."
${pythonPath} -c "from ai_scientist.perform_plotting import aggregate_plots; aggregate_plots('${experimentDir}', 'gpt-5-mini')" 2>&1 | while read line; do
  echo "$line"
  emit_event "ai.run.log" "$line"
done

emit_event "ai.run.log" "📄 Gathering citations..."
emit_event "ai.run.log" "✍️  Writing paper with gpt-5..."

${pythonPath} -m ai_scientist.perform_icbinb_writeup \\
  --folder "${experimentDir}" \\
  --model gpt-5-mini \\
  --big-model gpt-5 \\
  --num-cite-rounds 15 \\
  --page-limit 4 2>&1 | while read line; do
  echo "$line"
  emit_event "ai.run.log" "$line"
done

# Check if PDF was created
PDF_FILES=$(find "${experimentDir}" -maxdepth 1 -name "*.pdf" ! -name "*reflection*" | head -1)
if [ -n "$PDF_FILES" ]; then
  emit_event "ai.run.paper.generated" "✅ Paper PDF generated successfully"
  emit_event "ai.run.log" "📤 Uploading paper artifact..."
  
  # Upload artifact
  ${pythonPath} "${scriptPath}/upload_artifact_helper.py" "${id}" "$PDF_FILES" "${process.env.CONTROL_PLANE_URL || 'https://ai-scientist-v2-production.up.railway.app'}" && \
    emit_event "ai.run.log" "✅ Paper artifact uploaded" || \
    emit_event "ai.run.log" "⚠️  Artifact upload failed (check manually)"
else
  emit_event "ai.run.paper.failed" "❌ Paper generation failed - no PDF found"
fi

emit_event "ai.run.log" "✨ Writeup retry complete!"
`
    
    fs.writeFileSync(wrapperScript, wrapperContent, { mode: 0o755 })
    
    const child = spawn("/bin/bash", [wrapperScript], {
      detached: true,
      stdio: "ignore"
    })
    
    child.unref()
    
    await runsCollection.updateOne(
      { _id: id },
      { 
        $set: { 
          retryingWriteup: true,
          writeupRetryStartedAt: new Date()
        } 
      }
    )
    
    return NextResponse.json({
      message: "Paper generation retry started - watch live logs below",
      experimentDir: experimentDirs[experimentDirs.length - 1],
      pid: child.pid
    })
    
  } catch (error) {
    console.error("Error retrying writeup:", error)
    return NextResponse.json(
      { error: "Failed to retry writeup: " + (error as Error).message },
      { status: 500 }
    )
  }
}

