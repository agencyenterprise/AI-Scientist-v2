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

const StageProgressZ = z
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
  retryCount: z.number().int().optional()
})

export type Run = z.infer<typeof RunZ>
