"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { RUN_STATUSES } from "@/lib/state/constants"

export type HypothesisOption = {
  id: string
  title: string
}

export function RunsFilters({ hypotheses }: { hypotheses: HypothesisOption[] }) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const currentStatus = searchParams.get("status") ?? ""
  const currentHypothesis = searchParams.get("hypothesisId") ?? ""

  const pushParam = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams)
    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }
    params.delete("page")
    router.replace(`/runs?${params.toString()}`)
  }

  return (
    <div className="flex flex-wrap gap-4 rounded-lg border border-slate-800 bg-slate-900/40 p-4">
      <label className="flex flex-col text-sm text-slate-300">
        Status
        <select
          className="mt-1 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
          value={currentStatus}
          onChange={(event) => pushParam("status", event.target.value)}
        >
          <option value="">All</option>
          {RUN_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col text-sm text-slate-300">
        Hypothesis
        <select
          className="mt-1 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
          value={currentHypothesis}
          onChange={(event) => pushParam("hypothesisId", event.target.value)}
        >
          <option value="">All</option>
          {hypotheses.map((hypothesis) => (
            <option value={hypothesis.id} key={hypothesis.id}>
              {hypothesis.title}
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}
