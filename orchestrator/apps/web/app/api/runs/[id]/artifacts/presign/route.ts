import { NextRequest, NextResponse } from "next/server"
import { getEnv } from "@/lib/config/env"
import { Client } from "minio"

// Comprehensive MinIO logging helper
function logMinIO(level: 'INFO' | 'ERROR' | 'WARN', event: string, details: Record<string, unknown>) {
  const timestamp = new Date().toISOString()
  const logLine = `[${timestamp}] [MINIO] [${level}] ${event} | ${JSON.stringify(details)}`
  if (level === 'ERROR') {
    console.error(logLine)
  } else if (level === 'WARN') {
    console.warn(logLine)
  } else {
    console.log(logLine)
  }
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const startTime = Date.now()
  let runId: string = 'unknown'
  let action: string = 'unknown'
  let filename: string = 'unknown'
  
  try {
    const resolvedParams = await params
    runId = resolvedParams.id
    const body = await req.json()
    action = body.action
    filename = body.filename
    const { key, content_type } = body
    
    logMinIO('INFO', 'PRESIGN_REQUEST_START', {
      runId,
      action,
      filename,
      key: key || `runs/${runId}/${filename}`,
      content_type,
    })
    
    const env = getEnv()
    
    // Log MinIO connection details (without secrets)
    logMinIO('INFO', 'MINIO_CLIENT_INIT', {
      runId,
      endpoint: env.MINIO_ENDPOINT,
      port: env.MINIO_PORT,
      useSSL: env.MINIO_USE_SSL,
      bucket: env.MINIO_BUCKET,
    })
    
    const minioClient = new Client({
      endPoint: env.MINIO_ENDPOINT,
      port: env.MINIO_PORT,
      useSSL: env.MINIO_USE_SSL,
      accessKey: env.MINIO_ACCESS_KEY,
      secretKey: env.MINIO_SECRET_KEY
    })
    
    let url: string
    const objectKey = key || `runs/${runId}/${filename}`
    
    if (action === "put") {
      logMinIO('INFO', 'PRESIGN_PUT_START', { runId, objectKey, bucket: env.MINIO_BUCKET })
      
      try {
      url = await minioClient.presignedPutObject(
        env.MINIO_BUCKET,
        objectKey,
        24 * 60 * 60 // 24 hours
      )
        
        logMinIO('INFO', 'PRESIGN_PUT_SUCCESS', {
          runId,
          objectKey,
          urlLength: url.length,
          durationMs: Date.now() - startTime,
        })
      } catch (minioError) {
        logMinIO('ERROR', 'PRESIGN_PUT_MINIO_FAILED', {
          runId,
          objectKey,
          error: minioError instanceof Error ? minioError.message : String(minioError),
          errorType: minioError instanceof Error ? minioError.name : typeof minioError,
          stack: minioError instanceof Error ? minioError.stack?.split('\n').slice(0, 3).join(' | ') : undefined,
        })
        throw minioError
      }
      
    } else if (action === "get") {
      logMinIO('INFO', 'PRESIGN_GET_START', { runId, objectKey, bucket: env.MINIO_BUCKET })
      
      try {
      url = await minioClient.presignedGetObject(
        env.MINIO_BUCKET,
        objectKey,
        24 * 60 * 60 // 24 hours
      )
        
        logMinIO('INFO', 'PRESIGN_GET_SUCCESS', {
          runId,
          objectKey,
          urlLength: url.length,
          durationMs: Date.now() - startTime,
        })
      } catch (minioError) {
        logMinIO('ERROR', 'PRESIGN_GET_MINIO_FAILED', {
          runId,
          objectKey,
          error: minioError instanceof Error ? minioError.message : String(minioError),
          errorType: minioError instanceof Error ? minioError.name : typeof minioError,
          stack: minioError instanceof Error ? minioError.stack?.split('\n').slice(0, 3).join(' | ') : undefined,
        })
        throw minioError
      }
      
    } else {
      logMinIO('WARN', 'PRESIGN_INVALID_ACTION', { runId, action, filename })
      return NextResponse.json(
        { error: "Invalid action. Use 'put' or 'get'" },
        { status: 400 }
      )
    }
    
    logMinIO('INFO', 'PRESIGN_REQUEST_COMPLETE', {
      runId,
      action,
      filename,
      durationMs: Date.now() - startTime,
    })
    
    return NextResponse.json({ url })
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error)
    const errorType = error instanceof Error ? error.name : typeof error
    const errorStack = error instanceof Error ? error.stack?.split('\n').slice(0, 5).join(' | ') : undefined
    
    logMinIO('ERROR', 'PRESIGN_REQUEST_FAILED', {
      runId,
      action,
      filename,
      error: errorMessage,
      errorType,
      stack: errorStack,
      durationMs: Date.now() - startTime,
    })
    
    // Also log to stderr for Railway logs
    console.error(`[MINIO_CRITICAL] Presign failed for run=${runId} file=${filename} action=${action}: ${errorMessage}`)
    
    return NextResponse.json(
      { 
        error: errorMessage,
        details: {
          runId,
          action,
          filename,
          errorType,
        }
      },
      { status: 500 }
    )
  }
}
