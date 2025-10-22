import { getValidationQueue } from "@/lib/data/validations"
import { StatusBadge } from "@/components/StatusBadge"
import { ValidationSummary } from "@/components/ValidationSummary"
import { Pagination } from "@/components/Pagination"
import { extract } from "@/lib/utils/extract"

export const dynamic = "force-dynamic"

export default async function ValidationQueuePage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const params = await searchParams
  const page = parseInt(extract(params.page) ?? "1", 10) || 1
  const pageSize = 10
  const { items, total } = await getValidationQueue(page, pageSize)

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-slate-100">Validation Queue</h1>
        <p className="text-sm text-slate-400">
          Human reviewers evaluate the AI Scientist outputs here. Every entry reflects the latest
          MongoDB state.
        </p>
      </header>
      <div className="space-y-4">
        {items.length === 0 && (
          <p className="text-sm text-slate-500">No runs awaiting human validation.</p>
        )}
        {items.map(({ run, hypothesis, validations }) => {
          const auto = validations.find((validation) => validation.kind === "auto")
          const human = validations.find((validation) => validation.kind === "human")
          return (
            <article
              key={run._id}
              className="rounded-lg border border-slate-800 bg-slate-900/40 p-6"
            >
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-100">Run {run._id}</h2>
                  <p className="text-sm text-slate-300">{hypothesis?.title ?? "Unknown hypothesis"}</p>
                </div>
                <StatusBadge status={run.status} />
              </div>
              <div className="mt-4">
                <ValidationSummary auto={auto} human={human} />
              </div>
            </article>
          )
        })}
      </div>
      <Pagination total={total} page={page} pageSize={pageSize} />
    </div>
  )
}
