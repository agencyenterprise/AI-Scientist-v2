import { NextRequest, NextResponse } from "next/server"
import { CloudEventsEnvelopeZ, validateEventData } from "@/lib/schemas/cloudevents"
import { processEvent } from "@/lib/services/events.service"
import { isEventSeen, markEventSeen } from "@/lib/services/deduplication.service"
import { logger } from "@/lib/logging/logger"

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()

    const envelopeResult = CloudEventsEnvelopeZ.safeParse(body)
    if (!envelopeResult.success) {
      logger.warn({ errors: envelopeResult.error.errors }, "Invalid CloudEvents envelope")
      return NextResponse.json(
        {
          type: "about:blank",
          title: "Invalid CloudEvents envelope",
          status: 422,
          detail: envelopeResult.error.errors[0]?.message || "Invalid event format",
          instance: "/api/ingest/event"
        },
        { status: 422 }
      )
    }

    const event = envelopeResult.data

    if (!validateEventData(event.type, event.data)) {
      logger.warn({ 
        eventType: event.type, 
        eventData: event.data,
        runId: event.subject.replace("run/", "")
      }, "Event data validation failed")
      
      return NextResponse.json(
        {
          type: "about:blank",
          title: "Invalid event data",
          status: 422,
          detail: `Event data does not match schema for type: ${event.type}. Data: ${JSON.stringify(event.data)}`,
          instance: "/api/ingest/event"
        },
        { status: 422 }
      )
    }

    if (await isEventSeen(event.id)) {
      logger.info({ eventId: event.id }, "Duplicate event ignored")
      return NextResponse.json(
        {
          event_id: event.id,
          status: "duplicate"
        },
        { status: 201 }
      )
    }

    const runId = event.subject.replace("run/", "")
    await markEventSeen(event.id, runId)
    await processEvent(event)

    logger.info({ eventId: event.id, type: event.type }, "Event processed")

    return NextResponse.json(
      {
        event_id: event.id
      },
      { status: 201 }
    )
  } catch (error) {
    logger.error({ error }, "Error processing event")
    return NextResponse.json(
      {
        type: "about:blank",
        title: "Internal server error",
        status: 500,
        detail: error instanceof Error ? error.message : "Unknown error",
        instance: "/api/ingest/event"
      },
      { status: 500 }
    )
  }
}

