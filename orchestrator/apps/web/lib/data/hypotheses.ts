import { listHypotheses } from "../repos/hypotheses.repo"
import { serializeDates } from "../utils/serialize"

export async function getHypotheses(page = 1, pageSize = 50) {
  const result = await listHypotheses({}, page, pageSize)
  
  // Filter out test hypotheses (those with titles ending in "Test")
  const filteredResult = {
    ...result,
    items: result.items.filter(h => !h.title.endsWith(" Test")),
    total: result.items.filter(h => !h.title.endsWith(" Test")).length
  }
  
  return serializeDates(filteredResult)
}
