import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import { listEvents } from "@/lib/repos/events.repo"
import { isHttpError, toJsonResponse } from "@/lib/http/errors"

export const runtime = "nodejs"

const QuerySchema = z.object({
  page: z.coerce.number().min(1).default(1),
  pageSize: z.coerce.number().min(1).max(200).default(100)
})

export async function GET(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params
    const searchParams = Object.fromEntries(new URL(req.url).searchParams)
    const parsed = QuerySchema.safeParse(searchParams)
    if (!parsed.success) {
      return NextResponse.json(
        { message: "Invalid query", issues: parsed.error.issues },
        { status: 400 }
      )
    }
    const { items, total } = await listEvents(
      id,
      parsed.data.page,
      parsed.data.pageSize
    )
    return NextResponse.json({ items, total })
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
