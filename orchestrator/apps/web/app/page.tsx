import { getOverviewData } from "@/lib/data/overview"
import { RunTable } from "@/components/RunTable"
import { QueueStatus } from "@/components/QueueStatus"
import type { RunStatus } from "@/lib/state/constants"
import { formatDistanceToNow } from "date-fns"

export const dynamic = "force-dynamic"

export default async function OverviewPage() {
  const data = await getOverviewData()
  const statusOrder: RunStatus[] = [
    "QUEUED",
    "RUNNING",
    "AUTO_VALIDATING",
    "AWAITING_HUMAN",
    "FAILED"
  ]

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-10">
      <section>
        <h1 className="text-2xl font-semibold text-slate-100">Overview</h1>
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
          rows={data.latestRuns.map(({ run, hypothesis }) => ({
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
            {data.topHypotheses.map(({ hypothesis, runCount, lastRunAt }) => (
              <li
                key={hypothesis._id}
                className="rounded-lg border border-slate-800 bg-slate-900/40 p-4"
              >
                <div className="text-sm font-semibold text-slate-100">{hypothesis.title}</div>
                <p className="mt-1 text-xs text-slate-400">{hypothesis.idea}</p>
                <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
                  <span>{runCount} runs</span>
                  <span>Last run {formatDistanceToNow(new Date(lastRunAt), { addSuffix: true })}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
