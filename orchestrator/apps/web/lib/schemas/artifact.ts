import { z } from "zod"

export const ArtifactZ = z.object({
  _id: z.string().uuid(),
  runId: z.string().uuid(),
  key: z.string().min(1),
  uri: z.string().min(1),
  hash: z.string().optional(),
  sha256: z.string().optional(),  // SHA256 checksum for integrity verification
  size: z.number().int().nonnegative().optional(),
  contentType: z.string().optional(),
  kind: z.string().optional(),  // paper, archive, code, plot, figure, documentation, etc.
  createdAt: z.coerce.date(),
  description: z.string().optional(),
  seed: z.boolean().optional()
})

export type Artifact = z.infer<typeof ArtifactZ>
