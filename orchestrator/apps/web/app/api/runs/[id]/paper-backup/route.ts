import { NextRequest, NextResponse } from "next/server"
import { getDb } from "@/lib/db"

/**
 * GET /api/runs/[id]/paper-backup
 * 
 * Retrieves paper PDF from MongoDB base64 backup.
 * This is a fallback when MinIO artifacts are missing.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: runId } = await params
  
  try {
    const db = await getDb()
    
    // Find the final paper backup (prefer _final, otherwise any paper)
    const backups = await db.collection("paper_backups")
      .find({ runId })
      .sort({ is_final: -1, createdAt: -1 })
      .toArray()
    
    if (!backups || backups.length === 0) {
      return NextResponse.json(
        { error: "No paper backup found for this run" },
        { status: 404 }
      )
    }
    
    // Get query param for specific file or return the best one
    const requestedFile = request.nextUrl.searchParams.get("file")
    
    let backup = backups[0]
    if (requestedFile) {
      const match = backups.find(b => b.filename === requestedFile)
      if (match) backup = match
    }
    
    // If just listing, return metadata
    if (request.nextUrl.searchParams.get("list") === "true") {
      return NextResponse.json({
        backups: backups.map(b => ({
          filename: b.filename,
          kind: b.kind,
          is_final: b.is_final,
          size_bytes: b.size_bytes,
          createdAt: b.createdAt
        }))
      })
    }
    
    // Decode base64 and return PDF
    const pdfBuffer = Buffer.from(backup.pdf_base64, 'base64')
    
    return new NextResponse(pdfBuffer, {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `inline; filename="${backup.filename}"`,
        'Content-Length': String(pdfBuffer.length),
        'Cache-Control': 'public, max-age=31536000',
      },
    })
    
  } catch (error) {
    console.error("Error retrieving paper backup:", error)
    return NextResponse.json(
      { error: "Failed to retrieve paper backup" },
      { status: 500 }
    )
  }
}

