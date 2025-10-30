import { CreateHypothesisForm } from "@/components/CreateHypothesisForm"
import { HypothesisHistoryPanel } from "@/components/HypothesisHistoryPanel"
import { getHypotheses } from "@/lib/data/hypotheses"
import { Sparkles } from "lucide-react"

export const dynamic = "force-dynamic"

export default async function HomePage() {
  const { items: hypotheses } = await getHypotheses(1, 30)

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 py-8 md:flex-row md:py-12">
      <HypothesisHistoryPanel hypotheses={hypotheses} />

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
