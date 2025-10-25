"use client"

import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef } from "react"
import { STAGES, type StageName, type RunStatus } from "@/lib/state/constants"
import type { Validation } from "@/lib/schemas/validation"
import type { Stage } from "@/lib/schemas/stage"
import type { Artifact } from "@/lib/schemas/artifact"
import type { Run } from "@/lib/schemas/run"
import type { Hypothesis } from "@/lib/schemas/hypothesis"
import type { PaperAnalysis } from "@/lib/schemas/analysis"
import { StageProgress } from "@/components/StageProgress"
import { StatusBadge } from "@/components/StatusBadge"
import { RunEventsFeed } from "@/components/RunEventsFeed"
import { ArtifactList } from "@/components/ArtifactList"
import { ValidationSummary } from "@/components/ValidationSummary"
import { HumanValidationForm } from "@/components/HumanValidationForm"
import { RunActions } from "@/components/RunActions"
import { PaperAnalysisPanel } from "@/components/PaperAnalysisPanel"
import { ErrorDisplay } from "@/components/ErrorDisplay"
import { StageProgressPanel } from "@/components/StageProgressPanel"
import { StageTimingView } from "@/components/StageTimingView"
import { LiveLogViewer } from "@/components/LiveLogViewer"
import { PlotGallery } from "@/components/PlotGallery"

type RunDetail = {
  run: Run
  stages: Stage[]
  validations: Validation[]
  artifacts: Artifact[]
  hypothesis?: Hypothesis
  analysis?: PaperAnalysis | null
}

const TERMINAL_STATES: RunStatus[] = ["HUMAN_VALIDATED", "FAILED", "CANCELED"]

function logChanges(prev: RunDetail | undefined, current: RunDetail) {
  if (!prev) {
    console.log(`[Run ${current.run._id.slice(0, 8)}] Initial load - Status: ${current.run.status}`)
    return
  }

  const changes: string[] = []

  if (prev.run.status !== current.run.status) {
    changes.push(`Status: ${prev.run.status} → ${current.run.status}`)
  }

  if (prev.run.currentStage?.name !== current.run.currentStage?.name) {
    changes.push(`Stage: ${prev.run.currentStage?.name || "none"} → ${current.run.currentStage?.name || "none"}`)
  }

  if (prev.run.currentStage?.progress !== current.run.currentStage?.progress) {
    const prevProg = prev.run.currentStage?.progress || 0
    const currProg = current.run.currentStage?.progress || 0
    changes.push(`Progress: ${(prevProg * 100).toFixed(0)}% → ${(currProg * 100).toFixed(0)}%`)
  }

  if (prev.stages.length !== current.stages.length) {
    changes.push(`Stages: ${prev.stages.length} → ${current.stages.length}`)
  }

  if (prev.validations.length !== current.validations.length) {
    changes.push(`Validations: ${prev.validations.length} → ${current.validations.length}`)
  }

  if (prev.artifacts.length !== current.artifacts.length) {
    changes.push(`Artifacts: ${prev.artifacts.length} → ${current.artifacts.length}`)
  }

  if (changes.length > 0) {
    console.log(`[Run ${current.run._id.slice(0, 8)}] ${changes.join(" | ")}`)
  }
}

export function RunDetailClient({ initialData }: { initialData: RunDetail }) {
  const prevDataRef = useRef<RunDetail | undefined>(undefined)

  const { data } = useQuery({
    queryKey: ["run", initialData.run._id],
    queryFn: async () => {
      const res = await fetch(`/api/runs/${initialData.run._id}`)
      if (!res.ok) throw new Error("Failed to fetch run")
      return res.json() as Promise<RunDetail>
    },
    initialData,
    refetchInterval: (query) => {
      const currentData = query.state.data as RunDetail | undefined
      const isTerminal = currentData && TERMINAL_STATES.includes(currentData.run.status)
      return isTerminal ? false : 5000
    },
    refetchOnWindowFocus: true
  })

  useEffect(() => {
    logChanges(prevDataRef.current, data)
    prevDataRef.current = data
  }, [data])

  const detail = data
  const stageProgress = STAGES.map((name) => toStageProgress(name, detail))
  const autoValidation = detail.validations.find((v) => v.kind === "auto")
  const humanValidation = detail.validations.find((v) => v.kind === "human")
  const canCancel = ["QUEUED", "SCHEDULED", "STARTING", "RUNNING"].includes(detail.run.status)
  const canRetryWriteup = detail.run.status === "FAILED" || detail.run.status === "COMPLETED"
  const isTerminal = TERMINAL_STATES.includes(detail.run.status)

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-8">
      <header className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-100">Run {detail.run._id}</h1>
          <StatusBadge status={detail.run.status} />
          {!isTerminal && (
            <span className="text-xs text-slate-500">
              <span className="inline-block h-2 w-2 rounded-full bg-green-500 animate-pulse mr-1.5"></span>
              polling every 5s
            </span>
          )}
        </div>
        <div className="text-sm text-slate-400">
          Hypothesis: <span className="text-slate-200">{detail.hypothesis?.title ?? "Unknown"}</span>
        </div>
        <RunActions 
          runId={detail.run._id} 
          status={detail.run.status}
          canCancel={canCancel}
          canRetryWriteup={canRetryWriteup}
        />
      </header>

      <ErrorDisplay run={detail.run} />
      
      {detail.run.status === "RUNNING" && (
        <section className="grid gap-6 md:grid-cols-2">
          <StageProgressPanel run={detail.run} />
          <StageTimingView run={detail.run} />
        </section>
      )}

      <section className="grid gap-6 md:grid-cols-[2fr,1fr]">
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
          <h2 className="text-sm font-semibold text-slate-200">Pipeline Stages</h2>
          <div className="mt-4">
            <StageProgress stages={stageProgress} />
          </div>
        </div>
        <div className="space-y-6">
          <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
            <h2 className="text-sm font-semibold text-slate-200">Metadata</h2>
            <dl className="mt-4 grid gap-3 text-sm text-slate-300">
              <div className="flex justify-between">
                <dt>Created</dt>
                <dd>{new Date(detail.run.createdAt).toLocaleString()}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Updated</dt>
                <dd>{new Date(detail.run.updatedAt).toLocaleString()}</dd>
              </div>
              {detail.run.startedAt && (
                <div className="flex justify-between">
                  <dt>Started</dt>
                  <dd>{new Date(detail.run.startedAt).toLocaleString()}</dd>
                </div>
              )}
              {detail.run.completedAt && (
                <div className="flex justify-between">
                  <dt>Completed</dt>
                  <dd>{new Date(detail.run.completedAt).toLocaleString()}</dd>
                </div>
              )}
              {detail.run.pod?.id && (
                <div className="flex justify-between">
                  <dt>Pod</dt>
                  <dd className="font-mono text-xs">{detail.run.pod.id.slice(0, 12)}</dd>
                </div>
              )}
              {detail.run.pod?.instanceType && (
                <div className="flex justify-between">
                  <dt>Instance</dt>
                  <dd>{detail.run.pod.instanceType}</dd>
                </div>
              )}
            </dl>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
            <h2 className="text-sm font-semibold text-slate-200">Validations</h2>
            <div className="mt-4">
              <ValidationSummary auto={autoValidation} human={humanValidation} />
            </div>
          </div>
          {detail.analysis && (
            <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
              <h2 className="text-sm font-semibold text-slate-200">Paper analysis</h2>
              <div className="mt-4">
                <PaperAnalysisPanel analysis={detail.analysis} />
              </div>
            </div>
          )}
        </div>
      </section>

      <section>
        <PlotGallery runId={detail.run._id} />
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        <LiveLogViewer runId={detail.run._id} />
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
          <h2 className="text-sm font-semibold text-slate-200">Artifacts</h2>
          <div className="mt-4">
            <ArtifactList runId={detail.run._id} artifacts={detail.artifacts} />
          </div>
        </div>
      </section>
      
      <section>
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
          <h2 className="text-sm font-semibold text-slate-200">All Events</h2>
          <div className="mt-4">
            <RunEventsFeed runId={detail.run._id} />
          </div>
        </div>
      </section>

      {detail.run.status === "AWAITING_HUMAN" && (
        <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
          <h2 className="text-sm font-semibold text-slate-200">Human validation</h2>
          <div className="mt-4">
            <HumanValidationForm runId={detail.run._id} />
          </div>
        </section>
      )}
      {!detail.analysis && (
        <section className="rounded-lg border border-dashed border-slate-800 bg-slate-900/20 p-6 text-sm text-slate-400">
          Paper analysis has not been generated yet. Trigger it via the API once the paper draft is ready.
        </section>
      )}
    </div>
  )
}

function toStageProgress(name: StageName, detail: RunDetail) {
  const stage = detail.stages.find((item) => item.name === name)
  const current = detail.run.currentStage
  
  // Derive progress: use stage document, or current stage progress, or calculate from run status
  let progress = stage?.progress ?? (current?.name === name ? current.progress ?? 0 : 0)
  
  // Derive status: use stage document, or derive from run state
  let status = stage?.status ?? deriveStatus(name, detail.run.status, current?.name)
  
  // BANDAID FIX: If stage shows COMPLETED but has no progress, fill the bar
  // TODO: Fix root cause - why do stage_completed events fail to send/process?
  if (status === "COMPLETED" && progress === 0) {
    progress = 1.0
  }
  
  return {
    name,
    progress,
    status
  }
}

function deriveStatus(name: StageName, runStatus: string, currentName?: StageName) {
  // If run is completed, all stages should be completed
  if (runStatus === "COMPLETED") return "COMPLETED"
  
  if (currentName === name) return "RUNNING"
  const stageIndex = STAGES.indexOf(name)
  const currentIndex = currentName ? STAGES.indexOf(currentName) : -1
  if (currentIndex > stageIndex) return "COMPLETED"
  if (["FAILED", "CANCELED"].includes(runStatus)) {
    return currentIndex >= stageIndex ? "FAILED" : "PENDING"
  }
  return currentIndex >= stageIndex ? "COMPLETED" : "PENDING"
}

