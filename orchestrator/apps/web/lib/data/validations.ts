import { getDb } from "../db/mongo"
import { listValidationsForRuns } from "../repos/validations.repo"
import { findHypothesesByIds } from "../repos/hypotheses.repo"
import { serializeDates } from "../utils/serialize"
import { RunZ, type Run } from "../schemas/run"
import { type RunStatus } from "../state/constants"

export async function getValidationQueue(page = 1, pageSize = 25) {
  const queueStatuses: RunStatus[] = ["AWAITING_HUMAN", "COMPLETED"]
  const db = await getDb()
  const rawRuns = await db
    .collection<Run>("runs")
    .find({ hidden: { $ne: true }, status: { $in: queueStatuses } })
    .sort({ createdAt: -1 })
    .toArray()

  const runs = rawRuns.map((run) => RunZ.parse(run))
  const runIds = runs.map((run) => run._id)

  const validations = runIds.length > 0 ? await listValidationsForRuns(runIds) : []

  const validationsByRun = new Map<string, typeof validations>()
  for (const validation of validations) {
    const list = validationsByRun.get(validation.runId) ?? []
    list.push(validation)
    validationsByRun.set(validation.runId, list)
  }

  const filteredRuns = runs.filter((run) => {
    const runValidations = validationsByRun.get(run._id) ?? []
    const hasHumanValidation = runValidations.some((validation) => validation.kind === "human")
    if (hasHumanValidation) return false

    if (run.status === "AWAITING_HUMAN") return true

    if (run.status === "COMPLETED") {
      const hasAutoValidation = runValidations.some((validation) => validation.kind === "auto")
      const stageFourComplete =
        Boolean(run.stageTiming?.Stage_4) ||
        (run.currentStage?.name === "Stage_4" && (run.currentStage?.progress ?? 0) >= 1)

      return hasAutoValidation || stageFourComplete
    }

    return false
  })

  const total = filteredRuns.length
  const startIndex = (page - 1) * pageSize
  const paginatedRuns = filteredRuns.slice(startIndex, startIndex + pageSize)

  const hypotheses = paginatedRuns.length
    ? await findHypothesesByIds(paginatedRuns.map((run) => run.hypothesisId))
    : []
  const hypothesisMap = new Map(hypotheses.map((item) => [item._id, item]))

  const queueEntries = paginatedRuns.map((run) => ({
    run,
    hypothesis: hypothesisMap.get(run.hypothesisId),
    validations: validationsByRun.get(run._id) ?? []
  }))

  return serializeDates({
    items: queueEntries,
    total
  })
}
