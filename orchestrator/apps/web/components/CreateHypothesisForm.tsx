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

    // Extract and structure the conversation
    setExtracting(true)
    try {
      const response = await fetch("/api/hypotheses/extract-chatgpt", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ url })
      })

      const data = await response.json()

      if (!response.ok) {
        setError(data.error || "Failed to extract ChatGPT conversation")
        return
      }

      // Show modal with structured hypothesis
      setModalTitle(data.title || "")
      setModalDescription(data.description || data.rawText)
      setShowModal(true)
      setError(null)
    } catch (err) {
      setError("Network error while extracting conversation")
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
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="text-sm font-medium text-slate-300" htmlFor="title">
            Title
          </label>
          <input
            id="title"
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 disabled:opacity-50"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            disabled={extracting || pending}
            required
          />
        </div>
        <div>
          <label className="text-sm font-medium text-slate-300" htmlFor="idea">
            Idea
          </label>
          <textarea
            id="idea"
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 disabled:opacity-50"
            rows={4}
            value={idea}
            onChange={(event) => setIdea(event.target.value)}
            disabled={extracting || pending}
            required
          />
        </div>

        {/* OR Divider */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-700"></div>
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-slate-900/40 px-2 text-slate-400">OR</span>
          </div>
        </div>

        {/* ChatGPT URL Input */}
        <div>
          <label className="text-sm font-medium text-slate-300" htmlFor="chatgpt-url">
            Paste ChatGPT Share Link
          </label>
          <div className="mt-1 flex gap-2">
            <input
              id="chatgpt-url"
              type="url"
              placeholder="https://chatgpt.com/share/..."
              className="flex-1 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 disabled:opacity-50"
              value={chatGptUrl}
              onChange={(event) => handleChatGptUrlChange(event.target.value)}
              disabled={extracting || pending}
            />
            {extracting && (
              <div className="flex items-center px-3">
                <svg
                  className="animate-spin h-5 w-5 text-sky-400"
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
            <p className="mt-1 text-xs text-sky-400">
              Extracting and structuring conversation with AI...
            </p>
          )}
          {!extracting && (
            <p className="mt-1 text-xs text-slate-500">
              Paste a shared ChatGPT conversation URL to automatically extract and structure your hypothesis
            </p>
          )}
        </div>

        <div className="flex items-center gap-4">
          <button
            type="submit"
            className="rounded border border-sky-600/60 bg-sky-900/40 px-4 py-2 text-sm font-semibold text-sky-100 disabled:opacity-40"
            disabled={pending || extracting}
          >
            Create Hypothesis
          </button>
          {error && <span className="text-sm text-rose-400">{error}</span>}
        </div>
      </form>
    </>
  )
}
