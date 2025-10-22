"use client"

import { FormEvent, useState, useTransition } from "react"
import { useRouter } from "next/navigation"

export function CreateHypothesisForm() {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [title, setTitle] = useState("")
  const [idea, setIdea] = useState("")
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    startTransition(async () => {
      setError(null)
      const response = await fetch("/api/hypotheses", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, idea })
      })
      if (!response.ok) {
        const message = await response.text()
        setError(message || "Failed to create hypothesis")
        return
      }
      setTitle("")
      setIdea("")
      router.refresh()
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="text-sm font-medium text-slate-300" htmlFor="title">
          Title
        </label>
        <input
          id="title"
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          required
        />
      </div>
      <div>
        <label className="text-sm font-medium text-slate-300" htmlFor="idea">
          Idea
        </label>
        <textarea
          id="idea"
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
          rows={4}
          value={idea}
          onChange={(event) => setIdea(event.target.value)}
          required
        />
      </div>
      <div className="flex items-center gap-4">
        <button
          type="submit"
          className="rounded border border-sky-600/60 bg-sky-900/40 px-4 py-2 text-sm font-semibold text-sky-100 disabled:opacity-40"
          disabled={pending}
        >
          Create Hypothesis
        </button>
        {error && <span className="text-sm text-rose-400">{error}</span>}
      </div>
    </form>
  )
}
