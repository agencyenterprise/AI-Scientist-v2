import { cancelRun } from "@/lib/services/runs.service"
import { toJsonResponse, isHttpError, createNotFound } from "@/lib/http/errors"
import { findRunById } from "@/lib/repos/runs.repo"

export const runtime = "nodejs"

export async function POST(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params
    const run = await findRunById(id)
    if (!run) {
      throw createNotFound("Run not found")
    }
    await cancelRun(id)
    return new Response(null, { status: 204 })
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
