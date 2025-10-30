import Link from "next/link"
import { CreateHypothesisForm } from "@/components/CreateHypothesisForm"
import { StartRunButton } from "@/components/StartRunButton"
import { getHypotheses } from "@/lib/data/hypotheses"
import { formatDistanceToNow } from "date-fns"
import { Clock, Sparkles } from "lucide-react"

export const dynamic = "force-dynamic"

export default async function HomePage() {
  const { items: hypotheses } = await getHypotheses(1, 30)

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 py-8 md:flex-row md:py-12">
      <aside className="md:w-[26rem] md:flex-shrink-0">
        <div className="relative flex h-[calc(100vh-5rem)] flex-col overflow-hidden rounded-3xl border border-slate-800/80 bg-slate-950/60 shadow-[0_30px_90px_-45px_rgba(56,189,248,0.45)] md:sticky md:top-20">
          <div className="border-b border-slate-800/80 px-5 py-4">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-sky-500/15 text-sky-200">
                <Sparkles className="h-4 w-4" />
              </span>
              <div>
                <p className="text-xs uppercase tracking-widest text-slate-500">Recent</p>
                <p className="text-sm font-semibold text-slate-100">Hypothesis history</p>
              </div>
            </div>
          </div>
          <div className="custom-scrollbar flex-1 overflow-y-auto overscroll-contain px-5 py-4 pr-2">
            {hypotheses.length === 0 ? (
              <div className="rounded-[2rem] border border-dashed border-slate-800/80 bg-slate-900/60 p-6 text-center text-sm text-slate-500">
                Nothing here yet. Share your first idea to kick things off.
              </div>
            ) : (
              <ul className="space-y-4">
                {hypotheses.map((hypothesis) => {
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
                            <p className="mt-2 text-xs text-rose-300">
                              {ideation.error}
                            </p>
                          )}
                          <div className="mt-3 inline-flex items-center gap-2 whitespace-nowrap rounded-full border border-slate-800/80 bg-slate-900/70 px-3 py-1 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                            <Clock className="h-3 w-3 text-slate-400" />
                            {createdLabel}
                          </div>
                        </div>
                        <div className="flex flex-shrink-0 flex-col items-end gap-2">
                          <StartRunButton hypothesisId={hypothesis._id} disabled={runDisabled} />
                          {runDisabled && (
                            <span className="text-[10px] font-medium uppercase tracking-[0.25em] text-slate-500">
                              {ideationStatus && ideationStatus !== "COMPLETED"
                                ? "Ideation pending"
                                : "Idea not ready"}
                            </span>
                          )}
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
            )}
          </div>
        </div>
      </aside>

      <section className="relative flex-1">
        <div className="relative overflow-hidden rounded-[2.75rem] border border-slate-800/80 bg-slate-950/70 px-6 py-12 shadow-[0_50px_140px_-60px_rgba(14,165,233,0.9)] sm:px-12 sm:py-16">
          <div className="pointer-events-none absolute -left-[20%] -top-[35%] h-[420px] w-[420px] rounded-full bg-sky-500/20 blur-3xl" />
          <div className="pointer-events-none absolute -right-[25%] top-1/3 h-[360px] w-[360px] rounded-full bg-indigo-500/20 blur-3xl" />
          <div className="relative mx-auto flex max-w-3xl flex-col gap-10 text-center">
            <div className="flex flex-col items-center gap-4">
              <span className="inline-flex items-center gap-2 rounded-full border border-sky-500/40 bg-sky-500/15 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-sky-200">
                <Sparkles className="h-3.5 w-3.5" />
                Launch a hypothesis
              </span>
              <h1 className="text-balance text-4xl font-semibold text-white sm:text-5xl">
                What's on your mind?
              </h1>
              <p className="max-w-2xl text-pretty text-base text-slate-300 sm:text-lg">
                Describe the research direction you want the AI Scientist to explore, or drop a shared ChatGPT conversation to auto-extract the details.
              </p>
            </div>

            <div className="relative rounded-[28px] border border-slate-800/70 bg-slate-950/80 p-6 text-left shadow-[0_30px_80px_-50px_rgba(125,211,252,0.45)] backdrop-blur">
              <CreateHypothesisForm />
            </div>

            <p className="text-xs text-slate-500">
              Launch ideation or experiments instantly—updates stream back here in real time and are mirrored across the overview and runs dashboards.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
