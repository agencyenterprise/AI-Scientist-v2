import { z } from "zod"
import { RUN_STATUSES, STAGES } from "../state/constants"

const PodInfoZ = z
  .object({
    id: z.string().optional(),
    instanceType: z.string().optional(),
    region: z.string().optional()
  })
  .strict()
  .nullable()
  .optional()

// Normalize stage names from various formats to canonical names
const displayToCanonicalStage: Record<string, string> = {
  "Stage 1: Initial Implementation": "Stage_1",
  "Stage 1: Preliminary Investigation": "Stage_1",
  "Stage 2: Baseline Tuning": "Stage_2",
  "Stage 3: Creative Research": "Stage_3",
  "Stage 3: Research Agenda Execution": "Stage_3",
  "Stage 4: Ablation Studies": "Stage_4"
}

const StageProgressZ = z.preprocess(
  (val: any) => {
    // Handle null/undefined
    if (!val || typeof val !== 'object' || !val.name) return val
    
    // If it's already canonical, keep it
    if (STAGES.includes(val.name as any)) {
      return val
    }
    
    // Try to normalize from display name
    const normalized = displayToCanonicalStage[val.name]
    if (normalized) {
      return { ...val, name: normalized }
    }
    
    // Return as-is
    return val
  },
  z
    .object({
      name: z.enum(STAGES).optional(),
      progress: z.number().min(0).max(1).optional(),
      iteration: z.number().int().optional(),
      maxIterations: z.number().int().optional(),
      goodNodes: z.number().int().optional(),
      buggyNodes: z.number().int().optional(),
      totalNodes: z.number().int().optional(),
      bestMetric: z.string().optional()
    })
    .strict()
    .nullable()
    .optional()
)

const StageTimingZ = z.record(
  z.object({
    elapsed_s: z.number().int().optional(),
    duration_s: z.number().int().optional(),
    startedAt: z.coerce.date().optional(),
    completedAt: z.coerce.date().optional()
  })
).optional()

const NodeProgressZ = z.object({
  nodeId: z.string(),
  iteration: z.number().int(),
  isBuggy: z.boolean().optional(),
  metric: z.string().optional(),
  timestamp: z.coerce.date()
}).optional()

export const RunZ = z.object({
  _id: z.string().uuid(),
  hypothesisId: z.string().uuid(),
  status: z.enum(RUN_STATUSES),
  pod: PodInfoZ,
  currentStage: StageProgressZ,
  stageTiming: StageTimingZ,
  metrics: z.record(z.number()).optional(),
  nodeHistory: z.array(NodeProgressZ).optional(),
  createdAt: z.coerce.date(),
  updatedAt: z.coerce.date(),
  startedAt: z.coerce.date().optional(),
  completedAt: z.coerce.date().optional(),
  failedAt: z.coerce.date().optional(),
  lastHeartbeat: z.coerce.date().optional(),
  archivedAt: z.coerce.date().optional(),
  seed: z.boolean().optional(),
  lastEventSeq: z.number().int().optional(),
  claimedBy: z.string().optional(),
  claimedAt: z.coerce.date().optional(),
  errorType: z.string().nullable().optional(),
  errorMessage: z.string().nullable().optional(),
  retryCount: z.number().int().optional(),
  hidden: z.boolean().optional()
})

export type Run = z.infer<typeof RunZ>
