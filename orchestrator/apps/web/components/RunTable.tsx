import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import { StatusBadge } from "./StatusBadge"
import type { Run } from "@/lib/schemas/run"

export type RunTableRow = {
  run: Run
  hypothesisTitle?: string
}

export function RunTable({ rows }: { rows: RunTableRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-slate-400">No runs found.</p>
  }
  return (
    <div className="overflow-hidden rounded-lg border border-slate-800">
      <table className="min-w-full divide-y divide-slate-800">
        <thead className="bg-slate-900/60">
          <tr>
            <HeaderCell>ID</HeaderCell>
            <HeaderCell>Hypothesis</HeaderCell>
            <HeaderCell>Status</HeaderCell>
            <HeaderCell>Current Stage</HeaderCell>
            <HeaderCell>Age</HeaderCell>
            <HeaderCell>
              <span className="sr-only">Actions</span>
            </HeaderCell>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 bg-slate-950/40">
          {rows.map(({ run, hypothesisTitle }) => (
            <tr key={run._id} className="hover:bg-slate-900/40">
              <Cell>
                <code className="text-xs">{run._id}</code>
              </Cell>
              <Cell>{hypothesisTitle ?? "—"}</Cell>
              <Cell>
                <StatusBadge status={run.status} />
              </Cell>
              <Cell>
                {run.currentStage?.name ? (
                  <div className="text-xs text-slate-300">
                    <span className="font-medium text-slate-100">
                      {run.currentStage.name.replace("Stage_", "Stage ")}
                    </span>
                    <span className="ml-2 text-slate-400">
                      {Math.round(((run.currentStage.progress ?? 0) * 100) || 0)}%
                    </span>
                  </div>
                ) : (
                  <span className="text-xs text-slate-500">—</span>
                )}
              </Cell>
              <Cell>{formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })}</Cell>
              <Cell>
                <Link
                  href={`/runs/${run._id}`}
                  className="text-sm font-medium text-sky-400 hover:text-sky-300"
                >
                  View
                </Link>
              </Cell>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function HeaderCell({ children }: { children: React.ReactNode }) {
  return <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">{children}</th>
}

function Cell({ children }: { children: React.ReactNode }) {
  return <td className="px-4 py-3 text-sm text-slate-200">{children}</td>
}
