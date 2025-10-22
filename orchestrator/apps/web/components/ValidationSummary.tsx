import type { Validation } from "@/lib/schemas/validation"

export function ValidationSummary({ auto, human }: { auto?: Validation | null; human?: Validation | null }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <ValidationCard
        title="Auto Evaluation"
        validation={auto}
        emptyMessage="Awaiting automated verdict"
      />
      <ValidationCard
        title="Human Review"
        validation={human}
        emptyMessage="No human verdict yet"
      />
    </div>
  )
}

function ValidationCard({
  title,
  validation,
  emptyMessage
}: {
  title: string
  validation?: Validation | null
  emptyMessage: string
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
      <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
      {validation ? (
        <div className="mt-3 space-y-2 text-sm text-slate-300">
          <div className="text-slate-100">Verdict: {validation.verdict.toUpperCase()}</div>
          {validation.rubric && (
            <div className="space-y-1">
              <p className="text-xs text-slate-400">Rubric</p>
              <ul className="space-y-1 text-xs text-slate-300">
                {Object.entries(validation.rubric).map(([key, value]) => (
                  <li key={key} className="flex justify-between">
                    <span className="text-slate-400">{key}</span>
                    <span>{typeof value === "number" ? value.toFixed(2) : String(value)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {validation.notes && <p className="text-xs text-slate-400">Notes: {validation.notes}</p>}
          <p className="text-xs text-slate-500">
            Submitted {new Date(validation.createdAt).toLocaleString()}
          </p>
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-500">{emptyMessage}</p>
      )}
    </div>
  )
}
