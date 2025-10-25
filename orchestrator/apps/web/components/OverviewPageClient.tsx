"use client"

import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { RunTable } from "@/components/RunTable"
import { QueueStatus } from "@/components/QueueStatus"
import type { RunStatus } from "@/lib/state/constants"
import type { Run } from "@/lib/schemas/run"
import type { Hypothesis } from "@/lib/schemas/hypothesis"
import { formatDistanceToNow } from "date-fns"

type OverviewData = {
  counts: Record<RunStatus, number>
  queueStatus: { totalSlots: number; running: number; queued: number }
  latestRuns: Array<{ run: Run; hypothesis?: Hypothesis }>
  topHypotheses: Array<{ hypothesis: Hypothesis; runCount: number; lastRunAt: Date | string }>
}

function logChanges(prev: OverviewData | undefined, current: OverviewData) {
  if (!prev) {
    console.log(`[Overview] Queue: ${current.queueStatus.queued}Q/${current.queueStatus.running}R, Latest runs: ${current.latestRuns.length}`)
    return
  }

  const changes: string[] = []

  if (prev.queueStatus.queued !== current.queueStatus.queued) {
    changes.push(`Queued: ${prev.queueStatus.queued} → ${current.queueStatus.queued}`)
  }

  if (prev.queueStatus.running !== current.queueStatus.running) {
    changes.push(`Running: ${prev.queueStatus.running} → ${current.queueStatus.running}`)
  }

  const statusKeys: RunStatus[] = ["QUEUED", "RUNNING", "AUTO_VALIDATING", "AWAITING_HUMAN", "FAILED"]
  statusKeys.forEach((status) => {
    if (prev.counts[status] !== current.counts[status]) {
      changes.push(`${status}: ${prev.counts[status]} → ${current.counts[status]}`)
    }
  })

  if (changes.length > 0) {
    console.log(`[Overview] ${changes.join(" | ")}`)
  }
}

export function OverviewPageClient({ initialData }: { initialData: OverviewData }) {
  const prevDataRef = useRef<OverviewData | undefined>(undefined)

  const { data } = useQuery({
    queryKey: ["overview"],
    queryFn: async () => {
      const res = await fetch("/api/overview")
      if (!res.ok) throw new Error("Failed to fetch overview")
      return res.json() as Promise<OverviewData>
    },
    initialData,
    refetchInterval: 5000,
    refetchOnWindowFocus: true
  })

  useEffect(() => {
    logChanges(prevDataRef.current, data)
    prevDataRef.current = data
  }, [data])

  const statusOrder: RunStatus[] = [
    "QUEUED",
    "RUNNING",
    "AUTO_VALIDATING",
    "AWAITING_HUMAN",
    "FAILED"
  ]

  // Calculate estimated time for all queued and running experiments
  // Each experiment needs 1 full pod for ~6 hours
  const totalActiveExperiments = (data.counts.QUEUED ?? 0) + (data.counts.RUNNING ?? 0)
  const estimatedHours = totalActiveExperiments > 0 
    ? Math.ceil(totalActiveExperiments / data.queueStatus.totalSlots) * 6
    : 0

  return (
    <>
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-10">
        <section>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-slate-100">Overview</h1>
              <span className="text-xs text-slate-500">(polling every 5s)</span>
            </div>
            {totalActiveExperiments > 0 && (
              <div className="rounded-lg border border-slate-700 bg-slate-900/60 px-4 py-2">
                <p className="text-xs text-slate-400">
                  Estimated completion time:{" "}
                  <span className="font-semibold text-slate-200">
                    ~{estimatedHours} {estimatedHours === 1 ? 'hour' : 'hours'}
                  </span>
                </p>
                <p className="text-xs text-slate-500 mt-0.5">
                  ({totalActiveExperiments} {totalActiveExperiments === 1 ? 'experiment' : 'experiments'} @ 6hrs each, {data.queueStatus.totalSlots} {data.queueStatus.totalSlots === 1 ? 'pod' : 'pods'})
                </p>
              </div>
            )}
          </div>
          <p className="mt-2 text-sm text-slate-400">
            Real-time view over the AI Scientist pipeline sourced directly from MongoDB.
          </p>
          <div className="mt-6 grid gap-4 text-sm md:grid-cols-5">
            {statusOrder.map((status) => (
              <div key={status} className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
                <div className="text-xs uppercase text-slate-400">{status.replace(/_/g, " ")}</div>
                <div className="mt-2 text-2xl font-semibold text-slate-100">
                  {data.counts[status] ?? 0}
                </div>
              </div>
            ))}
          </div>
        </section>

        <QueueStatus
          totalSlots={data.queueStatus.totalSlots}
          running={data.queueStatus.running}
          queued={data.queueStatus.queued}
        />

        <section className="space-y-4">
          <header className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-slate-100">Latest Runs</h2>
            <a href="/runs" className="text-sm text-sky-400 hover:text-sky-300">
              View all
            </a>
          </header>
          <RunTable
            rows={data.latestRuns.map(({ run, hypothesis }: { run: Run; hypothesis?: Hypothesis }) => ({
              run,
              hypothesisTitle: hypothesis?.title
            }))}
          />
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold text-slate-100">Active Hypotheses</h2>
          {data.topHypotheses.length === 0 ? (
            <p className="text-sm text-slate-500">No recent runs linked to hypotheses.</p>
          ) : (
            <ul className="grid gap-4 md:grid-cols-2">
              {data.topHypotheses.map(({ hypothesis, runCount, lastRunAt }: { hypothesis: Hypothesis; runCount: number; lastRunAt: Date | string }) => (
                <HypothesisCard
                  key={hypothesis._id}
                  hypothesis={hypothesis}
                  runCount={runCount}
                  lastRunAt={lastRunAt}
                />
              ))}
            </ul>
          )}
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold text-slate-100">FAQ</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
              <h3 className="text-sm font-semibold text-slate-100">How long does each run take?</h3>
              <p className="mt-2 text-sm text-slate-400">Each experiment takes approximately 5-6 hours to complete.</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
              <h3 className="text-sm font-semibold text-slate-100">What happens if I create many hypotheses?</h3>
              <p className="mt-2 text-sm text-slate-400">
                All experiments share a pool of RunPod instances. If all pods are busy, new experiments will queue automatically until a pod becomes available.
              </p>
              <p className="mt-2 text-sm text-slate-400">
                Currently running with <span className="font-semibold text-slate-200">{data.queueStatus.totalSlots}</span> {data.queueStatus.totalSlots === 1 ? 'pod' : 'pods'}.
              </p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
              <h3 className="text-sm font-semibold text-slate-100">What can I see during the run?</h3>
              <p className="mt-2 text-sm text-slate-400">
                Click on any run to view real-time progress, including generated plots and charts as the experiment executes.
              </p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
              <h3 className="text-sm font-semibold text-slate-100">What are the final deliverables?</h3>
              <p className="mt-2 text-sm text-slate-400">
                When complete, each run produces a full research paper (PDF), all generated plots and experimental data, and the complete source code for reproducibility.
              </p>
            </div>
          </div>
        </section>
      </div>

      <div className="fixed bottom-8 right-8 flex flex-col items-center gap-2">
        <span className="text-sm font-medium text-slate-300">Create New</span>
        <Link
          href="/hypotheses"
          className="flex h-14 w-14 items-center justify-center rounded-full bg-sky-600 text-white shadow-lg transition-all hover:bg-sky-500 hover:shadow-xl hover:scale-110"
          title="Create new hypothesis"
        >
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </Link>
      </div>
    </>
  )
}

function HypothesisCard({
  hypothesis,
  runCount,
  lastRunAt
}: {
  hypothesis: Hypothesis
  runCount: number
  lastRunAt: Date | string
}) {
  const [isExpanded, setIsExpanded] = useState(false)
  const ideaPreview = hypothesis.idea.length > 150 
    ? hypothesis.idea.substring(0, 150) + "..." 
    : hypothesis.idea

  return (
    <li className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="text-sm font-semibold text-slate-100 flex-1">{hypothesis.title}</div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-slate-400 hover:text-slate-200 transition-colors"
          title={isExpanded ? "Collapse" : "Expand"}
        >
          <svg
            className={`h-5 w-5 transition-transform ${isExpanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>
      <p className="mt-1 text-xs text-slate-400">
        {isExpanded ? hypothesis.idea : ideaPreview}
      </p>
      <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
        <span>{runCount} runs</span>
        <span>Last run {formatDistanceToNow(new Date(lastRunAt), { addSuffix: true })}</span>
      </div>
    </li>
  )
}

