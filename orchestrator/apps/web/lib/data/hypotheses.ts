import { listHypotheses } from "../repos/hypotheses.repo"
import { serializeDates } from "../utils/serialize"

export async function getHypotheses(page = 1, pageSize = 50) {
  const result = await listHypotheses({}, page, pageSize)
  return serializeDates(result)
}
