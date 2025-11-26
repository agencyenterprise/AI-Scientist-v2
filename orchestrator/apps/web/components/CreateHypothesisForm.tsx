"use client"

import { FormEvent, useCallback, useEffect, useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { HypothesisConfirmationModal } from "./HypothesisConfirmationModal"

const IDEATION_LOCKED = false

export function CreateHypothesisForm() {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [title, setTitle] = useState("")
  const [idea, setIdea] = useState("")
  const [chatGptUrl, setChatGptUrl] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [extracting, setExtracting] = useState(false)
  const [extractionSuccess, setExtractionSuccess] = useState(false)
  const [extractionMessage, setExtractionMessage] = useState("")
  const [enableIdeation, setEnableIdeation] = useState(false)
  const [reflections, setReflections] = useState(5)
  const [maxNumGenerations, setMaxNumGenerations] = useState(1)
  const [ideationQueueSize, setIdeationQueueSize] = useState(0)
  
  // Additional context state
  const [enableAdditionalContext, setEnableAdditionalContext] = useState(false)
  const [additionalContext, setAdditionalContext] = useState("")
  
  // Modal state
  const [showModal, setShowModal] = useState(false)
  const [modalTitle, setModalTitle] = useState("")
  const [modalDescription, setModalDescription] = useState("")
  
  // Extraction view state
  const [showExtractionText, setShowExtractionText] = useState(false)
  const [extractedTextContent, setExtractedTextContent] = useState("")

  const refreshIdeationQueue = useCallback(async () => {
    try {
      const res = await fetch("/api/ideations/summary")
      if (!res.ok) {
        return
      }
      const data = await res.json()
      setIdeationQueueSize(data.counts?.QUEUED ?? 0)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    refreshIdeationQueue()
    const interval = window.setInterval(refreshIdeationQueue, 10000)
    return () => {
      window.clearInterval(interval)
    }
  }, [refreshIdeationQueue])

  const handleSuccessNavigation = (payload: any) => {
    // Show success message briefly on the current page
    setExtractionSuccess(true)
    
    const hasIdeation = !!payload?.ideation?.requestId
    const successMsg = hasIdeation 
      ? "✅ Hypothesis created & ideation queued!"
      : "✅ Hypothesis created! Run will start shortly."
    
    setExtractionMessage(successMsg)
    console.log(`[CreateHypothesisForm] Success: ideation=${hasIdeation}, message=${successMsg}`)
    
    // Clear form for next input
    setTitle("")
    setIdea("")
    setChatGptUrl("")
    setError(null)
    setEnableIdeation(false)
    setReflections(5)
    setMaxNumGenerations(1)
    setEnableAdditionalContext(false)
    setAdditionalContext("")
    
    if (hasIdeation) {
      refreshIdeationQueue()
    }
    
    // Hide success message after 3 seconds (stay on page)
    setTimeout(() => {
      setExtractionSuccess(false)
      setExtractionMessage("")
    }, 3000)
  }

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

  const handleChatGptUrlChange = (url: string) => {
    setChatGptUrl(url)
    setError(null)

    const validationError = validateChatGptUrl(url)
    if (validationError) {
      setError(validationError)
    }
  }

  const handleExtractAndIdeate = async () => {
    if (!chatGptUrl.trim()) {
      setError("Please paste a ChatGPT URL first")
      return
    }

    const validationError = validateChatGptUrl(chatGptUrl)
    if (validationError) {
      setError(validationError)
      return
    }

    // Create hypothesis with background extraction
    setExtracting(true)
    try {
      const ideationSelected = enableIdeation && !IDEATION_LOCKED
      console.log(`[CreateHypothesisForm] Extracting ChatGPT URL, enableIdeation=${ideationSelected}, reflections=${reflections}, maxNumGenerations=${maxNumGenerations}`)
      const response = await fetch("/api/hypotheses/extract-and-create", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          url: chatGptUrl,
          enableIdeation: enableIdeation && !IDEATION_LOCKED,
          reflections,
          maxNumGenerations: enableIdeation ? maxNumGenerations : 1,
          ...(enableAdditionalContext && additionalContext.trim() && { additionalContext: additionalContext.trim() })
        })
      })

      const data = await response.json().catch(() => null)

      if (!response.ok) {
        setError((data && data.error) || "Failed to create hypothesis from ChatGPT conversation")
        return
      }

      // Show success and continue
      handleSuccessNavigation(data)
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
          idea: confirmedDescription,
          enableIdeation: enableIdeation && !IDEATION_LOCKED,
          reflections,
          ...(enableAdditionalContext && additionalContext.trim() && { additionalContext: additionalContext.trim() })
        })
      })
      const data = await response.json().catch(() => null)
      if (!response.ok) {
        const message = (data && (data.message || data.error)) || (await response.text())
        setError(message || "Failed to create hypothesis")
        return
      }
      handleSuccessNavigation(data)
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
      const payload = {
        title,
        idea,
        enableIdeation: enableIdeation && !IDEATION_LOCKED,
        reflections,
        ...(enableAdditionalContext && additionalContext.trim() && { additionalContext: additionalContext.trim() })
      }
      const response = await fetch("/api/hypotheses", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload)
      })
      const data = await response.json().catch(() => null)
      if (!response.ok) {
        const message = (data && (data.message || data.error)) || (await response.text())
        setError(message || "Failed to create hypothesis")
        return
      }
      handleSuccessNavigation(data)
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

        {/* Additional Context Section */}
        <div className="space-y-3">
          <label
            className={`inline-flex w-fit items-center gap-3 rounded-full border border-slate-800/60 px-4 py-2 text-sm font-medium shadow-[0_12px_36px_-30px_rgba(14,165,233,0.2)] ${
              enableAdditionalContext
                ? "cursor-pointer bg-amber-900/40 text-amber-200 border-amber-600/40"
                : "cursor-pointer bg-slate-900/60 text-slate-200"
            }`}
          >
            <input
              type="checkbox"
              className="h-4 w-4 rounded-sm border-slate-600 bg-slate-900 text-amber-400 focus:ring-2 focus:ring-amber-400"
              checked={enableAdditionalContext}
              onChange={(event) => setEnableAdditionalContext(event.target.checked)}
              disabled={extracting || pending}
            />
            Add additional context
          </label>
          
          {enableAdditionalContext && (
            <div className="space-y-2">
              <p className="text-xs text-slate-500">
                This extra context will be passed to the experiment creation and refiner prompts. Use it for special instructions, constraints, or background information.
              </p>
              <textarea
                id="additionalContext"
                placeholder="Add any additional context, constraints, or special instructions for the AI Scientist. For example: preferred methods, specific datasets to use, constraints on the approach, or domain-specific knowledge."
                className="w-full min-h-[180px] resize-none rounded-3xl border border-amber-800/50 bg-slate-950/70 px-5 py-4 text-base leading-relaxed text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-amber-500/50 focus:ring-2 focus:ring-amber-400/20 disabled:opacity-50"
                rows={6}
                value={additionalContext}
                onChange={(event) => setAdditionalContext(event.target.value)}
                disabled={extracting || pending}
              />
            </div>
          )}
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
            <div className="relative flex-1">
              <input
                id="chatgpt-url"
                type="url"
                placeholder="https://chatgpt.com/share/..."
                className="w-full rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 pr-32 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-sky-500/50 focus:ring-2 focus:ring-sky-400/20 disabled:opacity-50"
                value={chatGptUrl}
                onChange={(event) => handleChatGptUrlChange(event.target.value)}
                disabled={extracting || pending}
              />
              {extracting && (
                <span className="pointer-events-none absolute right-2 top-1/2 inline-flex -translate-y-1/2 items-center gap-1 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.3em] text-sky-200">
                  <svg
                    className="h-3.5 w-3.5 animate-spin"
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
                  Extracting…
                </span>
              )}
            </div>
          </div>
          <p className={`mt-2 text-xs ${extracting ? "text-sky-200" : "text-slate-500"}`}>
            {extracting
              ? "Extracting the hypothesis from ChatGPT — this usually takes under 30 seconds. We’ll spin up a new run as soon as it’s ready."
              : "Paste a shared ChatGPT conversation URL to automatically extract and structure your hypothesis."}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-800/70 bg-slate-950/60 p-5">
          <div className="space-y-5">
            <div className="space-y-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                  Ideation assist
                </p>
                <p className="text-sm text-slate-300">
                  Once the hypothesis is created (either manually or from ChatGPT), we can queue a dedicated worker to brainstorm research variants before we run experiments.
                </p>
              </div>
              
              <div className="rounded-lg border border-slate-700/50 bg-slate-900/50 p-3">
                <p className="text-xs text-slate-400 mb-2">
                  <strong>Two paths:</strong>
                </p>
                <ul className="text-xs text-slate-400 space-y-1 ml-2">
                  <li>✅ <strong>Ideation enabled:</strong> Brainstorm variants first, then run experiments</li>
                  <li>⭕ <strong>Ideation disabled:</strong> Skip to experiments directly</li>
                </ul>
              </div>
              
              <p className="text-xs text-slate-500">
                {ideationQueueSize === 0
                  ? "Ideation queue is empty."
                  : `${ideationQueueSize} ideation ${ideationQueueSize === 1 ? "request" : "requests"} waiting.`}
              </p>
              <p className={`text-xs font-semibold ${enableIdeation ? "text-sky-400" : "text-slate-500"}`}>
                Status: {enableIdeation ? "✅ ENABLED (variants first)" : "⭕ DISABLED (experiments only)"}
              </p>
            </div>

            <div className="flex flex-col gap-4">
              <label
                className={`inline-flex w-fit items-center gap-3 rounded-full border border-slate-800/60 px-4 py-2 text-sm font-medium shadow-[0_12px_36px_-30px_rgba(14,165,233,0.2)] ${
                  IDEATION_LOCKED
                    ? "cursor-not-allowed bg-slate-800/40 text-slate-500"
                    : enableIdeation
                      ? "cursor-pointer bg-sky-900/40 text-sky-200 border-sky-600/40"
                      : "cursor-pointer bg-slate-900/60 text-slate-200"
                }`}
                title={IDEATION_LOCKED ? "Ideation is temporarily locked" : undefined}
              >
                <input
                  type="checkbox"
                  className={`h-4 w-4 rounded-sm border-slate-600 bg-slate-900 ${
                    IDEATION_LOCKED ? "text-slate-500" : "text-sky-400"
                  } focus:ring-2 focus:ring-sky-400`}
                  checked={enableIdeation && !IDEATION_LOCKED}
                  onChange={(event) => {
                    if (IDEATION_LOCKED) return
                    setEnableIdeation(event.target.checked)
                    console.log(`[CreateHypothesisForm] Ideation checkbox changed to: ${event.target.checked}`)
                  }}
                  disabled={extracting || pending || IDEATION_LOCKED}
                />
                Enable ideation
              </label>

              {IDEATION_LOCKED && (
                <p className="text-xs text-amber-400">
                  Ideation is temporarily unavailable.
                </p>
              )}

              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs uppercase tracking-[0.3em] text-slate-500">
                  <span>Reflections</span>
                  <span className="font-semibold text-slate-400">{reflections}</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={10}
                  value={reflections}
                  onChange={(event) => setReflections(Number.parseInt(event.target.value, 10))}
                  disabled={IDEATION_LOCKED || !enableIdeation || extracting || pending}
                  className="h-1 w-full appearance-none rounded-full bg-slate-800 accent-sky-400 disabled:cursor-not-allowed disabled:opacity-50"
                />
                <div className="flex justify-between text-[10px] uppercase tracking-[0.3em] text-slate-500">
                  <span>1</span>
                  <span>10</span>
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  How many refinement rounds to improve each idea. Minimum 5 recommended for reliable finalization. More rounds = better quality but slower.
                </p>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs uppercase tracking-[0.3em] text-slate-500">
                  <span>Max Ideas to Generate</span>
                  <span className="font-semibold text-slate-400">{maxNumGenerations}</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={20}
                  value={maxNumGenerations}
                  onChange={(event) => setMaxNumGenerations(Number.parseInt(event.target.value, 10))}
                  disabled={IDEATION_LOCKED || !enableIdeation || extracting || pending}
                  className="h-1 w-full appearance-none rounded-full bg-slate-800 accent-sky-400 disabled:cursor-not-allowed disabled:opacity-50"
                />
                <div className="flex justify-between text-[10px] uppercase tracking-[0.3em] text-slate-500">
                  <span>1</span>
                  <span>20</span>
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  Number of different research ideas to generate. Pick the best one to run experiments on.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {extractionSuccess ? (
            <div className="flex items-center gap-2 text-sm text-emerald-400 font-semibold">
              <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
              </svg>
              {extractionMessage}
            </div>
          ) : (
            <>
              {chatGptUrl.trim() ? (
                // ChatGPT extraction mode
                <button
                  type="button"
                  onClick={handleExtractAndIdeate}
                  disabled={extracting}
                  className="inline-flex items-center justify-center rounded-full bg-gradient-to-r from-sky-500 via-blue-500 to-cyan-400 px-6 py-3 text-sm font-semibold text-white shadow-[0_18px_40px_-18px_rgba(56,189,248,0.65)] transition hover:from-sky-400 hover:via-blue-400 hover:to-cyan-300 focus:outline-none focus:ring-2 focus:ring-sky-300 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:opacity-40"
                >
                  {extracting ? "Extracting..." : enableIdeation ? "Run Ideation" : "Extract Hypothesis"}
                </button>
              ) : (
                // Manual hypothesis mode
                <button
                  type="submit"
                  className="inline-flex items-center justify-center rounded-full bg-gradient-to-r from-sky-500 via-blue-500 to-cyan-400 px-6 py-3 text-sm font-semibold text-white shadow-[0_18px_40px_-18px_rgba(56,189,248,0.65)] transition hover:from-sky-400 hover:via-blue-400 hover:to-cyan-300 focus:outline-none focus:ring-2 focus:ring-sky-300 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:opacity-40"
                  disabled={pending || extracting}
                >
                  Launch Hypothesis
                </button>
              )}
              {error && <span className="text-sm text-rose-400">{error}</span>}
            </>
          )}
        </div>
      </form>

      {/* Extraction Text Viewer Modal */}
      {showExtractionText && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-2xl rounded-2xl border border-slate-700 bg-slate-950 p-6 max-h-[90vh] overflow-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-slate-100">
                📄 Extracted ChatGPT Conversation
              </h3>
              <button
                onClick={() => setShowExtractionText(false)}
                className="text-slate-400 hover:text-slate-200 transition"
              >
                ✕
              </button>
            </div>
            <div className="text-sm text-slate-300 font-mono whitespace-pre-wrap break-words bg-slate-900/50 rounded-lg p-4 max-h-[70vh] overflow-auto">
              {extractedTextContent || "No extraction data available"}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
