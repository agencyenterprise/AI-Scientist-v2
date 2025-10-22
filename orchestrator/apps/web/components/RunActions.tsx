"use client"

import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"

export function RunActions({ runId, canCancel }: { runId: string; canCancel: boolean }) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)

  if (!canCancel) {
    return null
  }

  const cancel = () => {
    if (!confirm("Cancel this run?")) return
    startTransition(async () => {
      setError(null)
      const response = await fetch(`/api/runs/${runId}/cancel`, {
        method: "POST"
      })
      if (!response.ok) {
        setError("Failed to cancel run")
        return
      }
      router.refresh()
    })
  }

  return (
    <div className="flex items-center gap-3">
      <button
        className="rounded border border-rose-600/60 bg-rose-900/40 px-4 py-2 text-sm font-semibold text-rose-100 disabled:opacity-40"
        onClick={cancel}
        disabled={pending}
      >
        Cancel Run
      </button>
      {error && <span className="text-sm text-rose-400">{error}</span>}
    </div>
  )
}
