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
    progress: z
      .number()
      .min(0)
      .max(1)
      .optional()
  })
  .strict()
  .nullable()
  .optional()

export const RunZ = z.object({
  _id: z.string().uuid(),
  hypothesisId: z.string().uuid(),
  status: z.enum(RUN_STATUSES),
  pod: PodInfoZ,
  currentStage: StageProgressZ,
  metrics: z.record(z.number()).optional(),
  createdAt: z.coerce.date(),
  updatedAt: z.coerce.date(),
  lastHeartbeat: z.coerce.date().optional(),
  archivedAt: z.coerce.date().optional(),
  seed: z.boolean().optional(),
  lastEventSeq: z.number().int().optional(),
  claimedBy: z.string().optional(),
  claimedAt: z.coerce.date().optional()
})

export type Run = z.infer<typeof RunZ>
