import { notFound } from "next/navigation"
import { getRunDetail } from "@/lib/data/runs"
import { STAGES, type StageName } from "@/lib/state/constants"
import type { Validation } from "@/lib/schemas/validation"
import type { Stage } from "@/lib/schemas/stage"
import { StageProgress } from "@/components/StageProgress"
import { StatusBadge } from "@/components/StatusBadge"
import { RunEventsFeed } from "@/components/RunEventsFeed"
import { ArtifactList } from "@/components/ArtifactList"
import { ValidationSummary } from "@/components/ValidationSummary"
import { HumanValidationForm } from "@/components/HumanValidationForm"
import { RunActions } from "@/components/RunActions"
import { PaperAnalysisPanel } from "@/components/PaperAnalysisPanel"

export const dynamic = "force-dynamic"

type RunDetail = NonNullable<Awaited<ReturnType<typeof getRunDetail>>>

export default async function RunDetailPage({ params }: { params: { id: string } }) {
  const detail = await getRunDetail(params.id)
  if (!detail) {
    notFound()
  }

  const stageProgress = STAGES.map((name) => toStageProgress(name, detail))
  const autoValidation = detail.validations.find((validation: Validation) => validation.kind === "auto")
  const humanValidation = detail.validations.find((validation: Validation) => validation.kind === "human")
  const canCancel = ["QUEUED", "SCHEDULED", "STARTING", "RUNNING"].includes(detail.run.status)

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-8">
      <header className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-100">Run {detail.run._id}</h1>
          <StatusBadge status={detail.run.status} />
        </div>
        <div className="text-sm text-slate-400">
          Hypothesis: <span className="text-slate-200">{detail.hypothesis?.title ?? "Unknown"}</span>
        </div>
        <RunActions runId={detail.run._id} canCancel={canCancel} />
      </header>

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
              {detail.run.pod?.id && (
                <div className="flex justify-between">
                  <dt>Pod</dt>
                  <dd>{detail.run.pod.id}</dd>
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

      <section className="grid gap-6 md:grid-cols-2">
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
          <h2 className="text-sm font-semibold text-slate-200">Events</h2>
          <div className="mt-4">
            <RunEventsFeed runId={detail.run._id} />
          </div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
          <h2 className="text-sm font-semibold text-slate-200">Artifacts</h2>
          <div className="mt-4">
            <ArtifactList runId={detail.run._id} artifacts={detail.artifacts} />
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
  const stage = detail.stages.find((item: Stage) => item.name === name)
  const current = detail.run.currentStage
  const progress = stage?.progress ?? (current?.name === name ? current.progress ?? 0 : 0)
  return {
    name,
    progress,
    status: stage?.status ?? deriveStatus(name, detail.run.status, current?.name)
  }
}

function deriveStatus(name: StageName, runStatus: string, currentName?: StageName) {
  if (currentName === name) return "RUNNING"
  const stageIndex = STAGES.indexOf(name)
  const currentIndex = currentName ? STAGES.indexOf(currentName) : -1
  if (currentIndex > stageIndex) return "COMPLETED"
  if (["FAILED", "CANCELED"].includes(runStatus)) {
    return currentIndex >= stageIndex ? "FAILED" : "PENDING"
  }
  return currentIndex >= stageIndex ? "COMPLETED" : "PENDING"
}
