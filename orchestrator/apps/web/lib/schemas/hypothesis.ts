import { z } from "zod"

export const HypothesisZ = z.object({
  _id: z.string().uuid(),
  title: z.string().min(3),
  idea: z.string().min(10),
  createdAt: z.coerce.date(),
  createdBy: z.string().min(1),
  updatedAt: z.coerce.date().optional(),
  seed: z.boolean().optional(),
  ideaJson: z.record(z.any()).optional()
})

export type Hypothesis = z.infer<typeof HypothesisZ>
