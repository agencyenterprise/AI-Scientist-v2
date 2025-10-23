"use client"

import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef } from "react"
import { RunsFilters } from "@/components/Filters"
import { Pagination } from "@/components/Pagination"
import { RunTable } from "@/components/RunTable"
import { EmptyState } from "@/components/EmptyState"
import { QueueStatus } from "@/components/QueueStatus"
import type { Run } from "@/lib/schemas/run"
import type { Hypothesis } from "@/lib/schemas/hypothesis"
import type { RunStatus } from "@/lib/state/constants"

type RunsPageData = {
  runs: { items: Run[]; total: number }
  hypotheses: { items: Hypothesis[] }
  queueStatus: { totalSlots: number; running: number; queued: number }
}

function logChanges(prev: RunsPageData | undefined, current: RunsPageData) {
  if (!prev) {
    console.log(`[Runs] Initial load - ${current.runs.items.length} runs, Queue: ${current.queueStatus.queued}Q/${current.queueStatus.running}R`)
    return
  }

  const changes: string[] = []

  if (prev.queueStatus.queued !== current.queueStatus.queued) {
    changes.push(`Queued: ${prev.queueStatus.queued} → ${current.queueStatus.queued}`)
  }

  if (prev.queueStatus.running !== current.queueStatus.running) {
    changes.push(`Running: ${prev.queueStatus.running} → ${current.queueStatus.running}`)
  }

  if (prev.runs.items.length !== current.runs.items.length) {
    changes.push(`Total: ${prev.runs.items.length} → ${current.runs.items.length}`)
  }

  const statusChanges = current.runs.items.filter((run, idx) => {
    const prevRun = prev.runs.items[idx]
    return prevRun && prevRun._id === run._id && prevRun.status !== run.status
  })

  if (statusChanges.length > 0) {
    statusChanges.forEach((run) => {
      const prevRun = prev.runs.items.find((r) => r._id === run._id)
      if (prevRun) {
        console.log(`[Run ${run._id.slice(0, 8)}] ${prevRun.status} → ${run.status}`)
      }
    })
  } else if (changes.length > 0) {
    console.log(`[Runs] ${changes.join(" | ")}`)
  }
}

export function RunsPageClient({
  initialData,
  status,
  hypothesisId,
  page
}: {
  initialData: RunsPageData
  status?: RunStatus
  hypothesisId?: string
  page: number
}) {
  const prevDataRef = useRef<RunsPageData | undefined>(undefined)

  const { data } = useQuery({
    queryKey: ["runs", status, hypothesisId, page],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (status) params.set("status", status)
      if (hypothesisId) params.set("hypothesisId", hypothesisId)
      if (page > 1) params.set("page", page.toString())

      const [runsRes, queueRes] = await Promise.all([
        fetch(`/api/runs?${params}`),
        fetch(`/api/runs?status=RUNNING&status=QUEUED`)
      ])

      const runs = await runsRes.json()
      const queueData = await queueRes.json()

      return {
        runs,
        hypotheses: initialData.hypotheses,
        queueStatus: {
          totalSlots: initialData.queueStatus.totalSlots,
          running: queueData.items?.filter((r: Run) => r.status === "RUNNING").length || 0,
          queued: queueData.items?.filter((r: Run) => r.status === "QUEUED").length || 0
        }
      } as RunsPageData
    },
    initialData,
    refetchInterval: 5000,
    refetchOnWindowFocus: true
  })

  useEffect(() => {
    logChanges(prevDataRef.current, data)
    prevDataRef.current = data
  }, [data])

  const rows = data.runs.items.map((run: Run) => ({
    run,
    hypothesisTitle: data.hypotheses.items.find((h: Hypothesis) => h._id === run.hypothesisId)?.title
  }))

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-8">
      <header className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-100">Runs</h1>
          <span className="text-xs text-slate-500">(polling every 5s)</span>
        </div>
        <p className="text-sm text-slate-400">
          Explore runs and monitor their progress through the orchestration pipeline.
        </p>
      </header>

      <QueueStatus
        totalSlots={data.queueStatus.totalSlots}
        running={data.queueStatus.running}
        queued={data.queueStatus.queued}
      />

      <RunsFilters
        hypotheses={data.hypotheses.items.map((h: Hypothesis) => ({ id: h._id, title: h.title }))}
      />
      {rows.length === 0 ? (
        <EmptyState title="No runs found" description="Adjust filters or launch a new run." />
      ) : (
        <RunTable rows={rows} />
      )}
      <Pagination total={data.runs.total} page={page} pageSize={25} />
    </div>
  )
}

