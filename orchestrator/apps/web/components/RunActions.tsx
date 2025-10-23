"use client"

import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"
import type { RunStatus } from "@/lib/state/constants"

export function RunActions({ 
  runId, 
  status,
  canCancel,
  canRetryWriteup 
}: { 
  runId: string
  status: RunStatus
  canCancel: boolean
  canRetryWriteup?: boolean
}) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const cancel = () => {
    if (!confirm("Cancel this run?")) return
    startTransition(async () => {
      setError(null)
      setSuccess(null)
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

  const retryWriteup = () => {
    if (!confirm("Retry paper generation for this run? Progress will appear in live logs below.")) return
    startTransition(async () => {
      setError(null)
      setSuccess(null)
      const response = await fetch(`/api/runs/${runId}/retry-writeup`, {
        method: "POST"
      })
      if (!response.ok) {
        const data = await response.json()
        setError(data.error || "Failed to start writeup retry")
        return
      }
      const data = await response.json()
      setSuccess("✅ " + data.message)
      setTimeout(() => {
        setSuccess(null)
        router.refresh()
      }, 3000)
    })
  }

  if (!canCancel && !canRetryWriteup) {
    return null
  }

  return (
    <div className="flex items-center gap-3">
      {canCancel && (
        <button
          className="rounded border border-rose-600/60 bg-rose-900/40 px-4 py-2 text-sm font-semibold text-rose-100 disabled:opacity-40"
          onClick={cancel}
          disabled={pending}
        >
          Cancel Run
        </button>
      )}
      {canRetryWriteup && (
        <button
          className="rounded border border-blue-600/60 bg-blue-900/40 px-4 py-2 text-sm font-semibold text-blue-100 disabled:opacity-40 hover:bg-blue-900/60"
          onClick={retryWriteup}
          disabled={pending}
        >
          Retry Paper Generation
        </button>
      )}
      {error && <span className="text-sm text-rose-400">{error}</span>}
      {success && <span className="text-sm text-emerald-400">{success}</span>}
    </div>
  )
}
