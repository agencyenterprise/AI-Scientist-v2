"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { Clock, Sparkles } from "lucide-react"
import { formatDistanceToNow } from "date-fns"
import { StartRunButton } from "./StartRunButton"
import type { Hypothesis } from "@/lib/schemas/hypothesis"

type HistoryHypothesis = Omit<Hypothesis, "createdAt" | "updatedAt"> & {
  createdAt: string
  updatedAt?: string
}

type HypothesisHistoryPanelProps = {
  hypotheses: HistoryHypothesis[]
}

export function HypothesisHistoryPanel({ hypotheses }: HypothesisHistoryPanelProps) {
  const [collapsed, setCollapsed] = useState(false)

  const visibleHypotheses = useMemo(
    () => hypotheses.filter((hypothesis) => !hypothesis.title.endsWith(" Test")),
    [hypotheses]
  )

  return (
    <aside className={`transition-all duration-300 ${collapsed ? "md:w-48" : "md:w-[26rem]"}`}>
      <div className="relative flex h-[calc(100vh-5rem)] flex-col overflow-hidden rounded-3xl border border-slate-800/80 bg-slate-950/60 shadow-[0_30px_90px_-45px_rgba(56,189,248,0.45)] md:sticky md:top-20">
        <div className="border-b border-slate-800/80 px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-sky-500/15 text-sky-200">
                <Sparkles className="h-4 w-4" />
              </span>
              <div>
                <p className="text-xs uppercase tracking-widest text-slate-500">Recent</p>
                <p className="text-sm font-semibold text-slate-100">Hypothesis history</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setCollapsed((prev) => !prev)}
              className="rounded-full border border-slate-700 bg-slate-900/60 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-300 transition hover:border-sky-500/60 hover:text-white"
            >
              {collapsed ? "Show" : "Hide"}
            </button>
          </div>
        </div>

        {collapsed ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 px-4 text-center text-xs text-slate-500">
            <p className="text-sm font-semibold text-slate-300">History hidden</p>
            <p>Tap “Show” to restore recent hypotheses.</p>
          </div>
        ) : visibleHypotheses.length === 0 ? (
          <div className="custom-scrollbar flex-1 overflow-y-auto overscroll-contain px-5 py-4 pr-2">
            <div className="rounded-[2rem] border border-dashed border-slate-800/80 bg-slate-900/60 p-6 text-center text-sm text-slate-500">
              Nothing here yet. Share your first idea to kick things off.
            </div>
          </div>
        ) : (
          <div className="custom-scrollbar flex-1 overflow-y-auto overscroll-contain px-5 py-4 pr-2">
            <ul className="space-y-4">
              {visibleHypotheses.map((hypothesis) => {
                const createdLabel = formatDistanceToNow(new Date(hypothesis.createdAt), {
                  addSuffix: true
                })
                const isExtracting = hypothesis.extractionStatus === "extracting"
                const ideation = hypothesis.ideation
                const ideationStatus = ideation?.status
                const primaryIdea =
                  ideationStatus === "COMPLETED" && Array.isArray(ideation?.ideas)
                    ? ideation.ideas[0]
                    : null
                const runDisabled =
                  !hypothesis.ideaJson ||
                  (!!ideationStatus && ideationStatus !== "COMPLETED")

                const ideationBadge = (() => {
                  if (!ideationStatus) return null
                  const baseClasses =
                    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                  switch (ideationStatus) {
                    case "QUEUED":
                      return (
                        <span className={`${baseClasses} bg-sky-500/10 text-sky-200`}>
                          ideation queued
                        </span>
                      )
                    case "RUNNING":
                      return (
                        <span className={`${baseClasses} bg-violet-500/10 text-violet-200`}>
                          ideation running
                        </span>
                      )
                    case "COMPLETED":
                      return (
                        <span className={`${baseClasses} bg-emerald-500/10 text-emerald-200`}>
                          ideation ready
                        </span>
                      )
                    case "FAILED":
                      return (
                        <span className={`${baseClasses} bg-rose-500/10 text-rose-200`}>
                          ideation failed
                        </span>
                      )
                    default:
                      return null
                  }
                })()

                return (
                  <li
                    key={hypothesis._id}
                    className="group relative w-full overflow-hidden rounded-[1.75rem] border border-slate-800/80 bg-slate-950/70 p-5 shadow-[0_25px_80px_-60px_rgba(56,189,248,0.65)] transition hover:-translate-y-0.5 hover:border-sky-500/50 hover:bg-slate-900/70"
                  >
                    <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-sky-500/10 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
                    <div className="relative flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold leading-snug text-slate-100 line-clamp-2 break-words">
                            {hypothesis.title}
                          </p>
                          {isExtracting && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
                              extracting
                            </span>
                          )}
                          {ideationBadge}
                        </div>
                        {primaryIdea ? (
                          <div className="mt-2 space-y-2">
                            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">
                              Ideation highlight
                            </p>
                            <p className="text-sm font-semibold text-sky-200">
                              {primaryIdea.Title}
                            </p>
                            <p className="line-clamp-4 whitespace-pre-line text-xs leading-relaxed text-slate-300">
                              {primaryIdea["Short Hypothesis"]}
                            </p>
                          </div>
                        ) : (
                          <p className="mt-2 line-clamp-4 whitespace-pre-line text-xs leading-relaxed text-slate-400">
                            {hypothesis.idea}
                          </p>
                        )}
                        {ideationStatus === "FAILED" && ideation?.error && (
                          <p className="mt-2 text-xs text-rose-300">{ideation.error}</p>
                        )}
                        <div className="mt-3 inline-flex items-center gap-2 whitespace-nowrap rounded-full border border-slate-800/80 bg-slate-900/70 px-3 py-1 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                          <Clock className="h-3 w-3 text-slate-400" />
                          {createdLabel}
                        </div>
                      </div>
                      <div className="flex flex-shrink-0 flex-col items-end gap-2">
                        <StartRunButton
                          hypothesisId={hypothesis._id}
                          disabled={runDisabled}
                          label="Launch Experiment"
                        />
                        {(ideationStatus || primaryIdea) && (
                          <Link
                            href={`/ideation?hypothesisId=${hypothesis._id}`}
                            className="inline-flex items-center justify-center rounded-full border border-sky-500/50 bg-sky-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-sky-100 transition hover:border-sky-400 hover:text-white"
                          >
                            View ideas
                          </Link>
                        )}
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          </div>
        )}
      </div>
    </aside>
  )
}
