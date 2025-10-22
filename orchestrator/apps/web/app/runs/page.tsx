import { getRunsPage, getQueueStatus } from "@/lib/data/runs"
import { getHypotheses } from "@/lib/data/hypotheses"
import { RUN_STATUSES, type RunStatus } from "@/lib/state/constants"
import { extract } from "@/lib/utils/extract"
import { RunsPageClient } from "@/components/RunsPageClient"

export const dynamic = "force-dynamic"

export default async function RunsPage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const params = await searchParams
  const statusParam = extract(params.status)
  const hypothesisId = extract(params.hypothesisId)
  const page = parseInt(extract(params.page) ?? "1", 10) || 1
  const status = isRunStatus(statusParam) ? (statusParam as RunStatus) : undefined
  
  const [runs, hypotheses, queueStatus] = await Promise.all([
    getRunsPage({
      status,
      hypothesisId: hypothesisId ?? undefined,
      page
    }),
    getHypotheses(1, 100),
    getQueueStatus()
  ])

  return (
    <RunsPageClient
      initialData={{ runs, hypotheses, queueStatus }}
      status={status}
      hypothesisId={hypothesisId ?? undefined}
      page={page}
    />
  )
}

function isRunStatus(value: string | undefined): value is RunStatus {
  return Boolean(value && RUN_STATUSES.includes(value as RunStatus))
}
