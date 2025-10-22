import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import { presignArtifactDownload, presignArtifactUpload } from "@/lib/services/artifacts.service"
import { createBadRequest, isHttpError, toJsonResponse } from "@/lib/http/errors"

export const runtime = "nodejs"

const RequestSchema = z.discriminatedUnion("action", [
  z.object({
    action: z.literal("put"),
    filename: z.string().min(1)
  }),
  z.object({
    action: z.literal("get"),
    key: z.string().min(1)
  })
])

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params
    const body = await req.json()
    const parsed = RequestSchema.safeParse(body)
    if (!parsed.success) {
      throw createBadRequest("Invalid payload", { issues: parsed.error.issues })
    }
    if (parsed.data.action === "put") {
      const result = await presignArtifactUpload(id, parsed.data.filename)
      return NextResponse.json(result)
    }
    const result = await presignArtifactDownload(parsed.data.key)
    return NextResponse.json(result)
  } catch (error) {
    return handleError(error)
  }
}

function handleError(error: unknown) {
  if (error instanceof Response) {
    return error
  }
  if (isHttpError(error)) {
    return toJsonResponse(error)
  }
  return new Response(JSON.stringify({ message: "Internal Server Error" }), {
    status: 500,
    headers: { "content-type": "application/json" }
  })
}
