import { getHypotheses } from "@/lib/data/hypotheses"
import { type Hypothesis } from "@/lib/schemas/hypothesis"
import { CreateHypothesisForm } from "@/components/CreateHypothesisForm"
import { StartRunButton } from "@/components/StartRunButton"
import { formatDistanceToNow } from "date-fns"

export const dynamic = "force-dynamic"

export default async function HypothesesPage() {
  const { items } = await getHypotheses(1, 50)

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-8">
      <header className="grid gap-6 md:grid-cols-[2fr,1fr]">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Hypotheses</h1>
          <p className="mt-2 text-sm text-slate-400">
            Catalog of research hypotheses orchestrated by the AI Scientist.
          </p>
          <ul className="mt-6 space-y-4">
            {items.map((hypothesis: Hypothesis) => {
              const isExtracting = hypothesis.extractionStatus === "extracting"
              return (
                <li
                  key={hypothesis._id}
                  className="rounded-lg border border-slate-800 bg-slate-900/40 p-4"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-lg font-semibold text-slate-100">{hypothesis.title}</h2>
                        {isExtracting && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-400">
                            <span className="animate-pulse">●</span>
                            Extracting...
                          </span>
                        )}
                      </div>
                      <p className="mt-2 text-sm text-slate-300">{hypothesis.idea}</p>
                      <p className="mt-2 text-xs text-slate-500">
                        Created {formatDistanceToNow(new Date(hypothesis.createdAt), { addSuffix: true })}
                      </p>
                    </div>
                    <StartRunButton hypothesisId={hypothesis._id} />
                  </div>
                </li>
              )
            })}
            {items.length === 0 && (
              <li className="rounded-lg border border-dashed border-slate-700 bg-slate-900/40 p-10 text-center text-sm text-slate-500">
                No hypotheses yet. Create the first one to get started.
              </li>
            )}
          </ul>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
          <h2 className="text-sm font-semibold text-slate-200">Create hypothesis</h2>
          <p className="mt-2 text-xs text-slate-400">
            Provide a title and detailed research idea. A run will be automatically queued when you create the hypothesis.
          </p>
          <div className="mt-4">
            <CreateHypothesisForm />
          </div>
        </div>
      </header>
    </div>
  )
}
