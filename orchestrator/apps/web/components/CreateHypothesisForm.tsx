"use client"

import { FormEvent, useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { HypothesisConfirmationModal } from "./HypothesisConfirmationModal"
import { IdeationPreviewModal } from "./IdeationPreviewModal"

interface IdeationResult {
  Name: string
  Title: string
  "Short Hypothesis": string
  Abstract: string
  "Related Work"?: string
  Experiments?: string | string[]
  "Risk Factors and Limitations"?: string | string[]
  [key: string]: any
}

export function CreateHypothesisForm() {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [title, setTitle] = useState("")
  const [idea, setIdea] = useState("")
  const [chatGptUrl, setChatGptUrl] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [extracting, setExtracting] = useState(false)
  const [runningIdeation, setRunningIdeation] = useState(false)
  
  // Modal state for ChatGPT extraction
  const [showModal, setShowModal] = useState(false)
  const [modalTitle, setModalTitle] = useState("")
  const [modalDescription, setModalDescription] = useState("")

  // Modal state for ideation preview
  const [showIdeationModal, setShowIdeationModal] = useState(false)
  const [ideationResult, setIdeationResult] = useState<IdeationResult | null>(null)
  const [pendingRunId, setPendingRunId] = useState<string | null>(null)

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
    
    // Submit immediately after closing modal (ChatGPT extraction path - skip ideation)
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
      
      // Get the created hypothesis and run
      const data = await response.json()
      
      // Clear form and redirect to run page
      setTitle("")
      setIdea("")
      setChatGptUrl("")
      
      // Redirect to the run page
      router.push(`/runs/${data.run._id}`)
      router.refresh()
    })
  }

  const handleModalCancel = () => {
    setShowModal(false)
    setChatGptUrl("")
  }

  const handleIdeationConfirm = (confirmedIdeaJson: IdeationResult) => {
    setShowIdeationModal(false)
    
    // Create hypothesis with the confirmed ideaJson
    startTransition(async () => {
      setError(null)
      const response = await fetch("/api/hypotheses", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ 
          title: confirmedIdeaJson.Title, 
          idea: confirmedIdeaJson.Abstract,
          ideaJson: confirmedIdeaJson
        })
      })
      if (!response.ok) {
        const message = await response.text()
        setError(message || "Failed to create hypothesis")
        return
      }
      
      const data = await response.json()
      
      // Clear form and redirect to run page
      setTitle("")
      setIdea("")
      setChatGptUrl("")
      setIdeationResult(null)
      
      router.push(`/runs/${data.run._id}`)
      router.refresh()
    })
  }

  const handleIdeationCancel = () => {
    setShowIdeationModal(false)
    setIdeationResult(null)
    setRunningIdeation(false)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setRunningIdeation(true)

    try {
      // First, run the ideation pipeline
      console.log("Running ideation pipeline...")
      const ideationResponse = await fetch("/api/ideation/preview", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, idea })
      })

      if (!ideationResponse.ok) {
        const errorData = await ideationResponse.json()
        setError(errorData.error || "Failed to generate research proposal")
        setRunningIdeation(false)
        return
      }

      const ideationData = await ideationResponse.json()
      
      if (!ideationData.success || !ideationData.idea) {
        setError("Failed to generate research proposal")
        setRunningIdeation(false)
        return
      }

      // Show the ideation result in a modal for confirmation
      setIdeationResult(ideationData.idea)
      setShowIdeationModal(true)
      setRunningIdeation(false)

    } catch (err) {
      console.error("Error during ideation:", err)
      setError("Network error while generating research proposal")
      setRunningIdeation(false)
    }
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

      <IdeationPreviewModal
        isOpen={showIdeationModal}
        ideationResult={ideationResult}
        onConfirm={handleIdeationConfirm}
        onCancel={handleIdeationCancel}
        originalTitle={title}
        originalIdea={idea}
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
            disabled={extracting || pending || runningIdeation}
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
            disabled={extracting || pending || runningIdeation}
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
              disabled={extracting || pending || runningIdeation}
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
            className="rounded border border-sky-600/60 bg-sky-900/40 px-4 py-2 text-sm font-semibold text-sky-100 disabled:opacity-40 flex items-center gap-2"
            disabled={pending || extracting || runningIdeation}
          >
            {runningIdeation && (
              <svg
                className="animate-spin h-4 w-4"
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
            )}
            {runningIdeation ? "Generating Research Proposal..." : "Create Hypothesis"}
          </button>
          {error && <span className="text-sm text-rose-400">{error}</span>}
        </div>
        {runningIdeation && (
          <p className="text-xs text-sky-400">
            Running ideation pipeline with literature search and reflection... This may take 1-2 minutes.
          </p>
        )}
      </form>
    </>
  )
}
