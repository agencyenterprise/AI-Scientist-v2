import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import { createHypothesis, listHypotheses } from "@/lib/repos/hypotheses.repo"
import { createBadRequest, isHttpError, toJsonResponse } from "@/lib/http/errors"
import { enqueueRun } from "@/lib/services/runs.service"
import { randomUUID } from "node:crypto"

export const runtime = "nodejs"

const CreateHypothesisSchema = z.object({
  title: z.string().min(3),
  idea: z.string().min(10),
  createdBy: z.string().min(1).default("system")
})

const QuerySchema = z.object({
  page: z.coerce.number().min(1).default(1),
  pageSize: z.coerce.number().min(1).max(100).default(50)
})

export async function GET(req: NextRequest) {
  try {
    const url = new URL(req.url)
    const parsed = QuerySchema.safeParse(Object.fromEntries(url.searchParams))
    if (!parsed.success) {
      return NextResponse.json(
        { message: "Invalid query", issues: parsed.error.issues },
        { status: 400 }
      )
    }
    const { items, total } = await listHypotheses({}, parsed.data.page, parsed.data.pageSize)
    return NextResponse.json({
      items,
      total,
      page: parsed.data.page,
      pageSize: parsed.data.pageSize
    })
  } catch (error) {
    return handleError(error)
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const parsed = CreateHypothesisSchema.safeParse(body)
    if (!parsed.success) {
      throw createBadRequest("Invalid payload", { issues: parsed.error.issues })
    }
    const hypothesis = await createHypothesis({
      _id: randomUUID(),
      title: parsed.data.title,
      idea: parsed.data.idea,
      createdAt: new Date(),
      createdBy: parsed.data.createdBy
    })
    
    await enqueueRun(hypothesis._id)
    
    return NextResponse.json(hypothesis, { status: 201 })
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
