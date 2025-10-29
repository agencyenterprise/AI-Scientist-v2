import { countRunsByStatus, getHypothesisActivity, listRuns } from "../repos/runs.repo"
import { findHypothesesByIds } from "../repos/hypotheses.repo"
import { type RunStatus } from "../state/constants"
import { serializeDates } from "../utils/serialize"
import { getEnv } from "../config/env"

const DASHBOARD_STATUSES: RunStatus[] = [
  "QUEUED",
  "RUNNING",
  "AUTO_VALIDATING",
  "AWAITING_HUMAN",
  "FAILED"
]

// In-memory cache for last stale run check
let lastStaleRunCheck = 0
const STALE_CHECK_INTERVAL_MS = 5 * 60 * 1000 // 5 minutes
const HEARTBEAT_TIMEOUT_MS = 5 * 60 * 1000 // 5 minutes without heartbeat = dead

async function checkForStaleRuns() {
  const now = Date.now()
  
  // Only check if we haven't checked in the last 5 minutes
  if (now - lastStaleRunCheck < STALE_CHECK_INTERVAL_MS) {
    return
  }
  
  try {
    const { getDb } = await import("../db/mongo")
    const db = await getDb()
    
    // Find RUNNING runs that haven't sent a heartbeat in 5+ minutes
    const staleThreshold = new Date(now - HEARTBEAT_TIMEOUT_MS)
    
    const staleRuns = await db.collection("runs").find({
      status: "RUNNING",
      $or: [
        { lastHeartbeat: { $lt: staleThreshold } },
        { lastHeartbeat: { $exists: false } } // No heartbeat ever recorded
      ]
    }).toArray()
    
    if (staleRuns.length > 0) {
      console.log(`⚠️ Found ${staleRuns.length} stale run(s) - marking as FAILED`)
      
      // Mark all stale runs as FAILED
      const result = await db.collection("runs").updateMany(
        {
          _id: { $in: staleRuns.map(r => r._id) },
          status: "RUNNING" // Double-check they're still RUNNING
        },
        {
          $set: {
            status: "FAILED",
            failedAt: new Date(),
            failureReason: "Worker heartbeat timeout (no heartbeat received in 5 minutes)"
          }
        }
      )
      
      console.log(`✓ Marked ${result.modifiedCount} stale run(s) as FAILED`)
    }
    
    lastStaleRunCheck = now
  } catch (error) {
    console.error("Error checking for stale runs:", error)
    // Don't throw - we don't want to break the overview endpoint
  }
}

export async function getOverviewData() {
  // Check for stale runs (lightweight, cached check)
  await checkForStaleRuns()
  const env = getEnv()
  const [{ items: latestRuns }, counts, activity] = await Promise.all([
    listRuns({}, 1, 10),
    countRunsByStatus(DASHBOARD_STATUSES),
    getHypothesisActivity(5)
  ])

  const hypothesisIds = new Set<string>()
  for (const item of activity) {
    hypothesisIds.add(item.hypothesisId)
  }
  for (const run of latestRuns) {
    hypothesisIds.add(run.hypothesisId)
  }

  const hypotheses = await findHypothesesByIds([...hypothesisIds])
  const hypothesisById = new Map(hypotheses.map((hypothesis) => [hypothesis._id, hypothesis]))

  const topHypotheses = activity
    .map((item) => ({
      hypothesis: hypothesisById.get(item.hypothesisId),
      runCount: item.runCount,
      lastRunAt: item.lastRunAt
    }))
    .filter(
      (item): item is { hypothesis: NonNullable<typeof item.hypothesis>; runCount: number; lastRunAt: Date } =>
        item.hypothesis !== undefined && !item.hypothesis.title.endsWith(" Test")
    )

  return serializeDates({
    counts,
    queueStatus: {
      totalSlots: env.MAX_POD_SLOTS,
      running: counts.RUNNING ?? 0,
      queued: counts.QUEUED ?? 0
    },
    latestRuns: latestRuns.map((run) => ({
      run,
      hypothesis: hypothesisById.get(run.hypothesisId)
    })),
    topHypotheses
  })
}
