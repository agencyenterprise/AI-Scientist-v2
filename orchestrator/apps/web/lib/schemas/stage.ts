import { z } from "zod"
import { STAGES } from "../state/constants"

export const StageStatusZ = z.enum(["PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"])

export const StageZ = z.object({
  _id: z.string().uuid(),
  runId: z.string().uuid(),
  index: z.number().int().min(0).max(3),
  name: z.enum(STAGES),
  status: StageStatusZ,
  progress: z.number().min(0).max(1).default(0),
  startedAt: z.coerce.date().optional(),
  completedAt: z.coerce.date().optional(),
  summary: z.string().nullable().optional(),
  seed: z.boolean().optional()
})

export type Stage = z.infer<typeof StageZ>
