"use client"

import { type Run } from "@/lib/schemas/run"

interface ErrorDisplayProps {
  run: Run
}

export function ErrorDisplay({ run }: ErrorDisplayProps) {
  if (run.status !== "FAILED" || !run.errorMessage) {
    return null
  }

  return (
    <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-6">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          <svg className="h-5 w-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-red-300">Experiment Failed</h3>
          
          <div className="mt-2">
            <p className="text-xs font-medium text-red-400">{run.errorType}</p>
            <p className="mt-1 text-sm text-red-200">{run.errorMessage}</p>
          </div>
          
          {run.failedAt && (
            <p className="mt-3 text-xs text-slate-400">
              Failed at {new Date(run.failedAt).toLocaleString()}
            </p>
          )}
          
          <div className="mt-4 flex gap-3">
            <button className="rounded bg-red-600/20 px-3 py-1.5 text-xs font-medium text-red-300 hover:bg-red-600/30">
              View Full Traceback
            </button>
            <button className="rounded bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700">
              Retry Run
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

