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

export async function getOverviewData() {
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
        Boolean(item.hypothesis) && !item.hypothesis.title.endsWith(" Test")
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
