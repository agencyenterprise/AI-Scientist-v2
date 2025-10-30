import { serializeDates } from "../utils/serialize"
import {
  listIdeationRequests,
  countIdeationByStatus
} from "../repos/ideations.repo"
import { findHypothesesByIds } from "../repos/hypotheses.repo"
import { type IdeationStatus } from "../schemas/ideation"

export async function getIdeationRequests(
  page = 1,
  pageSize = 25,
  status?: IdeationStatus,
  hypothesisId?: string
) {
  const filter: Record<string, unknown> = {}
  if (status) {
    filter.status = status
  }
  if (hypothesisId) {
    filter.hypothesisId = hypothesisId
  }

  const [{ items, total }, queued, running, completed, failed] = await Promise.all([
    listIdeationRequests(filter, page, pageSize),
    countIdeationByStatus("QUEUED"),
    countIdeationByStatus("RUNNING"),
    countIdeationByStatus("COMPLETED"),
    countIdeationByStatus("FAILED")
  ])

  const hypothesisIds = Array.from(new Set(items.map((item) => item.hypothesisId)))
  const hypotheses = await findHypothesesByIds(hypothesisIds)
  const hypothesisMap = new Map(hypotheses.map((hypothesis) => [hypothesis._id, hypothesis]))

  return serializeDates({
    items: items.map((item) => ({
      ...item,
      hypothesis: hypothesisMap.get(item.hypothesisId) ?? null
    })),
    total,
    page,
    pageSize,
    counts: {
      QUEUED: queued,
      RUNNING: running,
      COMPLETED: completed,
      FAILED: failed
    }
  })
}
