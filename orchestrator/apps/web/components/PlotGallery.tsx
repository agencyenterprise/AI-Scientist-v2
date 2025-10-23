"use client"

import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import type { Artifact } from "@/lib/schemas/artifact"

interface PlotGalleryProps {
  runId: string
}

export function PlotGallery({ runId }: PlotGalleryProps) {
  const [selectedPlot, setSelectedPlot] = useState<string | null>(null)
  
  const { data: artifacts } = useQuery<Artifact[]>({
    queryKey: ["artifacts", runId, "plot"],
    queryFn: async () => {
      const res = await fetch(`/api/runs/${runId}/artifacts`)
      if (!res.ok) throw new Error("Failed to fetch artifacts")
      const data = await res.json()
      return data.filter((a: Artifact) => a.contentType?.startsWith("image/"))
    },
    refetchInterval: 5000
  })

  const plots = artifacts || []

  if (plots.length === 0) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
        <h3 className="text-sm font-semibold text-slate-200">Plots</h3>
        <p className="mt-4 text-sm text-slate-400">No plots generated yet...</p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
      <h3 className="text-sm font-semibold text-slate-200">
        Plots <span className="text-xs text-slate-400">({plots.length} images)</span>
      </h3>
      
      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {plots.map((plot) => (
          <button
            key={plot._id}
            onClick={() => setSelectedPlot(plot.uri)}
            className="group relative aspect-square overflow-hidden rounded border border-slate-700 bg-slate-950 transition-all hover:border-sky-500"
          >
            <img
              src={`/api/artifacts/${plot.key}`}
              alt={plot.key.split('/').pop()}
              className="h-full w-full object-cover"
            />
            <div className="absolute inset-0 bg-black/60 opacity-0 transition-opacity group-hover:opacity-100">
              <div className="flex h-full items-center justify-center">
                <span className="text-xs font-medium text-white">View</span>
              </div>
            </div>
          </button>
        ))}
      </div>
      
      {selectedPlot && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-8"
          onClick={() => setSelectedPlot(null)}
        >
          <div className="relative max-h-full max-w-4xl">
            <button
              className="absolute -right-4 -top-4 rounded-full bg-slate-900 p-2 text-slate-400 hover:text-slate-200"
              onClick={() => setSelectedPlot(null)}
            >
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <img
              src={`/api/artifacts/${selectedPlot}`}
              alt="Plot"
              className="max-h-full rounded-lg"
            />
          </div>
        </div>
      )}
    </div>
  )
}

