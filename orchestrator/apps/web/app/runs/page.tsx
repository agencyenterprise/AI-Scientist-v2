import { RunsFilters } from "@/components/Filters"
import { Pagination } from "@/components/Pagination"
import { RunTable } from "@/components/RunTable"
import { EmptyState } from "@/components/EmptyState"
import { QueueStatus } from "@/components/QueueStatus"
import { getRunsPage, getQueueStatus } from "@/lib/data/runs"
import { getHypotheses } from "@/lib/data/hypotheses"
import { RUN_STATUSES, type RunStatus } from "@/lib/state/constants"
import { extract } from "@/lib/utils/extract"

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
  
  const [{ items, total }, hypotheses, queueStatus] = await Promise.all([
    getRunsPage({
      status,
      hypothesisId: hypothesisId ?? undefined,
      page
    }),
    getHypotheses(1, 100),
    getQueueStatus()
  ])

  const rows = items.map((run) => ({
    run,
    hypothesisTitle: hypotheses.items.find((hypothesis) => hypothesis._id === run.hypothesisId)?.title
  }))

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-slate-100">Runs</h1>
        <p className="text-sm text-slate-400">Explore runs and monitor their progress through the orchestration pipeline.</p>
      </header>
      
      <QueueStatus
        totalSlots={queueStatus.totalSlots}
        running={queueStatus.running}
        queued={queueStatus.queued}
      />
      
      <RunsFilters
        hypotheses={hypotheses.items.map((hypothesis) => ({ id: hypothesis._id, title: hypothesis.title }))}
      />
      {rows.length === 0 ? (
        <EmptyState title="No runs found" description="Adjust filters or launch a new run." />
      ) : (
        <RunTable rows={rows} />
      )}
      <Pagination total={total} page={page} pageSize={25} />
    </div>
  )
}

function isRunStatus(value: string | undefined): value is RunStatus {
  return Boolean(value && RUN_STATUSES.includes(value as RunStatus))
}
