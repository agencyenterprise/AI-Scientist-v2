"use client"

import { FormEvent, useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { HypothesisConfirmationModal } from "./HypothesisConfirmationModal"

export function CreateHypothesisForm() {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [title, setTitle] = useState("")
  const [idea, setIdea] = useState("")
  const [chatGptUrl, setChatGptUrl] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [extracting, setExtracting] = useState(false)
  
  // Modal state
  const [showModal, setShowModal] = useState(false)
  const [modalTitle, setModalTitle] = useState("")
  const [modalDescription, setModalDescription] = useState("")

  const validateChatGptUrl = (url: string): string | null => {
    if (!url.trim()) return null
    
    if (!url.includes('chatgpt.com')) {
      return "URL must be from chatgpt.com"
    }
    
    if (!url.includes('/share/')) {
      return "ChatGPT conversation must be shared and public. Click the share button in ChatGPT and use that URL."
    }
    
    return null
  }

  const handleChatGptUrlChange = async (url: string) => {
    setChatGptUrl(url)
    setError(null)

    const validationError = validateChatGptUrl(url)
    if (validationError) {
      setError(validationError)
      return
    }

    if (!url.trim()) {
      return
    }

    // Create hypothesis with background extraction
    setExtracting(true)
    try {
      const response = await fetch("/api/hypotheses/extract-and-create", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ url })
      })

      const data = await response.json()

      if (!response.ok) {
        setError(data.error || "Failed to create hypothesis from ChatGPT conversation")
        return
      }

      // Clear form and redirect immediately
      // Extraction continues in background
      setTitle("")
      setIdea("")
      setChatGptUrl("")
      router.push("/")
      router.refresh()
    } catch (err) {
      setError("Network error while creating hypothesis")
    } finally {
      setExtracting(false)
    }
  }

  const handleModalConfirm = (confirmedTitle: string, confirmedDescription: string) => {
    // Set the values from the modal
    setTitle(confirmedTitle)
    setIdea(confirmedDescription)
    setShowModal(false)
    
    // Submit immediately after closing modal
    startTransition(async () => {
      setError(null)
      const response = await fetch("/api/hypotheses", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ 
          title: confirmedTitle, 
          idea: confirmedDescription 
        })
      })
      if (!response.ok) {
        const message = await response.text()
        setError(message || "Failed to create hypothesis")
        return
      }
      // Clear form and redirect
      setTitle("")
      setIdea("")
      setChatGptUrl("")
      router.push("/")
      router.refresh()
    })
  }

  const handleModalCancel = () => {
    setShowModal(false)
    setChatGptUrl("")
  }

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
      setChatGptUrl("")
      router.push("/")
      router.refresh()
    })
  }

  return (
    <>
      <HypothesisConfirmationModal
        isOpen={showModal}
        title={modalTitle}
        description={modalDescription}
        onConfirm={handleModalConfirm}
        onCancel={handleModalCancel}
      />

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-2">
          <label className="text-sm font-semibold uppercase tracking-wide text-slate-300" htmlFor="title">
            Hypothesis title
          </label>
          <input
            id="title"
            placeholder="Summarize the scientific direction in one line"
            className="w-full rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-base text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-sky-500/50 focus:ring-2 focus:ring-sky-400/20 disabled:opacity-50"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            disabled={extracting || pending}
            required
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-semibold uppercase tracking-wide text-slate-300" htmlFor="idea">
            Hypothesis details
          </label>
          <textarea
            id="idea"
            placeholder="Explain the objective, expected insight, and why it matters. The more detail you include, the more context the AI Scientist has to work with."
            className="w-full min-h-[220px] resize-none rounded-3xl border border-slate-800 bg-slate-950/70 px-5 py-4 text-base leading-relaxed text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-sky-500/50 focus:ring-2 focus:ring-sky-400/20 disabled:opacity-50 md:min-h-[260px]"
            rows={8}
            value={idea}
            onChange={(event) => setIdea(event.target.value)}
            disabled={extracting || pending}
            required
          />
        </div>

        <div className="relative py-4">
          <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-gradient-to-r from-transparent via-slate-800/80 to-transparent" />
          <span className="relative mx-auto flex w-fit items-center gap-2 rounded-full border border-slate-800/80 bg-slate-950 px-4 py-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-400">
            or
          </span>
        </div>

        <div className="rounded-2xl border border-slate-800/70 bg-slate-950/60 p-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <label
              className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400"
              htmlFor="chatgpt-url"
            >
              Paste chatgpt share link
            </label>
            <p className="text-xs text-slate-500">
              We&apos;ll extract the title and summary automatically.
            </p>
          </div>
          <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-center">
            <input
              id="chatgpt-url"
              type="url"
              placeholder="https://chatgpt.com/share/..."
              className="flex-1 rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-sky-500/50 focus:ring-2 focus:ring-sky-400/20 disabled:opacity-50"
              value={chatGptUrl}
              onChange={(event) => handleChatGptUrlChange(event.target.value)}
              disabled={extracting || pending}
            />
            {extracting && (
              <div className="flex items-center px-1 text-sky-300">
                <svg
                  className="h-5 w-5 animate-spin"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
              </div>
            )}
          </div>
          {extracting && (
            <p className="mt-1 text-xs text-sky-300">
              Extracting and structuring conversation with AI...
            </p>
          )}
          {!extracting && (
            <p className="mt-1 text-xs text-slate-500">
              Paste a shared ChatGPT conversation URL to automatically extract and structure your hypothesis.
            </p>
          )}
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <button
            type="submit"
            className="inline-flex items-center justify-center rounded-full bg-gradient-to-r from-sky-500 via-blue-500 to-cyan-400 px-6 py-3 text-sm font-semibold text-white shadow-[0_18px_40px_-18px_rgba(56,189,248,0.65)] transition hover:from-sky-400 hover:via-blue-400 hover:to-cyan-300 focus:outline-none focus:ring-2 focus:ring-sky-300 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:opacity-40"
            disabled={pending || extracting}
          >
            Launch hypothesis
          </button>
          {error && <span className="text-sm text-rose-400">{error}</span>}
        </div>
      </form>
    </>
  )
}
