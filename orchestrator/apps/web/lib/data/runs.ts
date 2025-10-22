import { type RunStatus } from "../state/constants"
import { listRuns, findRunById, countRunsByStatus } from "../repos/runs.repo"
import { listStagesForRun } from "../repos/stages.repo"
import { listValidationsForRun } from "../repos/validations.repo"
import { listArtifactsForRun } from "../repos/artifacts.repo"
import { findHypothesisById } from "../repos/hypotheses.repo"
import { getPaperAnalysisByRunId } from "../repos/paperAnalyses.repo"
import { serializeDates } from "../utils/serialize"
import { getEnv } from "../config/env"

export async function getRunsPage(params: {
  status?: RunStatus
  hypothesisId?: string
  page?: number
  pageSize?: number
}) {
  const { status, hypothesisId, page = 1, pageSize = 25 } = params
  const result = await listRuns(
    {
      status,
      hypothesisId
    },
    page,
    pageSize
  )
  return serializeDates(result)
}

export async function getRunDetail(runId: string) {
  const run = await findRunById(runId)
  if (!run) {
    return null
  }
  const [stages, validations, artifacts, hypothesis, analysis] = await Promise.all([
    listStagesForRun(runId),
    listValidationsForRun(runId),
    listArtifactsForRun(runId),
    findHypothesisById(run.hypothesisId),
    getPaperAnalysisByRunId(runId)
  ])
  return serializeDates({
    run,
    stages,
    validations,
    artifacts,
    hypothesis,
    analysis
  })
}

export async function getQueueStatus() {
  const env = getEnv()
  const counts = await countRunsByStatus(["RUNNING", "QUEUED"])
  
  return {
    totalSlots: env.MAX_POD_SLOTS,
    running: counts.RUNNING ?? 0,
    queued: counts.QUEUED ?? 0
  }
}
