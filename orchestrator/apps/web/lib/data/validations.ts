import { listRuns } from "../repos/runs.repo"
import { listValidationsForRuns } from "../repos/validations.repo"
import { findHypothesesByIds } from "../repos/hypotheses.repo"
import { serializeDates } from "../utils/serialize"

export async function getValidationQueue(page = 1, pageSize = 25) {
  const { items: runs, total } = await listRuns({ status: "AWAITING_HUMAN" }, page, pageSize)
  const [validations, hypotheses] = await Promise.all([
    listValidationsForRuns(runs.map((run) => run._id)),
    findHypothesesByIds(runs.map((run) => run.hypothesisId))
  ])

  const validationsByRun = new Map<string, typeof validations>()
  for (const validation of validations) {
    const list = validationsByRun.get(validation.runId) ?? []
    list.push(validation)
    validationsByRun.set(validation.runId, list)
  }
  const hypothesisMap = new Map(hypotheses.map((item) => [item._id, item]))

  const queueEntries = runs.map((run) => ({
    run,
    hypothesis: hypothesisMap.get(run.hypothesisId),
    validations: validationsByRun.get(run._id) ?? []
  }))

  return serializeDates({
    items: queueEntries,
    total
  })
}
