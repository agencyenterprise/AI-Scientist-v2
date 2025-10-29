import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import OpenAI from "openai"
import { randomUUID } from "node:crypto"
import { ChatGPTSharedExtractor } from "@/lib/services/chatgpt-extractor.service"
import { getEnv } from "@/lib/config/env"
import { createHypothesis, updateHypothesis } from "@/lib/repos/hypotheses.repo"
import { enqueueRun } from "@/lib/services/runs.service"

export const runtime = "nodejs"

const ExtractAndCreateSchema = z.object({
  url: z.string().url().refine(
    (url) => url.includes('chatgpt.com') && url.includes('/share/'),
    {
      message: "URL must be a shared ChatGPT conversation (must contain chatgpt.com/share/)"
    }
  )
})

const HYPOTHESIS_EXTRACTION_PROMPT = `You are a scientific reasoning assistant. Your goal is to read a conversation transcript and turn it into a precise experimental hypothesis and description that a technical team can later use to design and run experiments.

Assume the reader or experimenter has **no prior context** about the conversation, the domain, or the systems discussed. 
Your output must therefore be fully self-contained: explain all concepts, terms, and goals as if to an intelligent reader encountering the topic for the first time.

Ignore casual dialogue or irrelevant material. Focus only on technical content such as definitions, systems, variables, constraints, intended mechanisms, and measurable outcomes.

Do NOT write code or full paper sections. Your job ends at producing a clear, testable, self-contained hypothesis that can later inform code generation or experimentation.

OUTPUT FORMAT (as JSON):
{
  "title": "A concise one-line title summarizing the main experimental idea",
  "hypothesis": "A clear statement of what is being tested, written as a cause–effect or measurable relationship. Include expected outcome, variables, and what is being compared or manipulated.",
  "experimentSummary": "1–3 paragraphs describing: What the system or method is (brief background so a newcomer can follow), what variables or parameters will be manipulated or measured, what metrics or observations will indicate success or failure, and why the experiment matters or what insight it aims to produce.",
  "keyTerms": "Define any technical or domain-specific terms or acronyms so the reader can understand the hypothesis without needing any external context. (Optional, can be empty string if not needed)"
}

Return ONLY valid JSON matching this structure.`

async function structureHypothesisWithLLM(conversationText: string): Promise<{
  title: string
  description: string
}> {
  const env = getEnv()
  
  if (!env.OPENAI_API_KEY) {
    throw new Error("OPENAI_API_KEY not configured")
  }

  const openai = new OpenAI({
    apiKey: env.OPENAI_API_KEY
  })

  // Use full conversation - GPT-5 can handle large contexts
  // No truncation needed
  const completion = await openai.chat.completions.create({
    model: "gpt-5-mini",
    messages: [
      {
        role: "system",
        content: HYPOTHESIS_EXTRACTION_PROMPT
      },
      {
        role: "user",
        content: conversationText
      }
    ],
    response_format: { type: "json_object" },
    temperature: 1
  })

  const content = completion.choices[0].message.content
  if (!content) {
    throw new Error("No content in OpenAI response")
  }

  const parsed = JSON.parse(content) as {
    title?: string
    hypothesis?: string
    experimentSummary?: string
    keyTerms?: string
  }

  // Build the full description
  let description = ""
  
  if (parsed.hypothesis) {
    description += `# Hypothesis\n${parsed.hypothesis}\n\n`
  }
  
  if (parsed.experimentSummary) {
    description += `# Experiment Summary\n${parsed.experimentSummary}\n\n`
  }
  
  if (parsed.keyTerms && parsed.keyTerms.trim()) {
    description += `# Key Terms\n${parsed.keyTerms}`
  }

  return {
    title: parsed.title || "",
    description: description.trim() || conversationText
  }
}

async function processExtractionInBackground(hypothesisId: string, url: string) {
  try {
    const extractor = new ChatGPTSharedExtractor()
    const extractedText = await extractor.extractPlainText(url)

    if (!extractedText || extractedText.trim().length === 0) {
      await updateHypothesis(hypothesisId, {
        extractionStatus: "failed",
        idea: "Failed to extract content from ChatGPT conversation"
      })
      return
    }

    // Structure the conversation using LLM
    const structured = await structureHypothesisWithLLM(extractedText)

    // Build ideaJson
    const ideaJson = {
      Name: structured.title.toLowerCase().replace(/\s+/g, "_"),
      Title: structured.title,
      "Short Hypothesis": structured.description.slice(0, 200),
      Abstract: structured.description,
      Experiments: [
        "Implement the proposed approach",
        "Test on relevant datasets",
        "Evaluate performance metrics"
      ],
      "Risk Factors and Limitations": [
        "Computational complexity",
        "Generalization to other domains"
      ]
    }

    // Update the hypothesis with extracted content
    await updateHypothesis(hypothesisId, {
      title: structured.title,
      idea: structured.description,
      ideaJson,
      extractionStatus: "completed"
    })

    // Enqueue a run for the hypothesis
    await enqueueRun(hypothesisId)

  } catch (error) {
    console.error("Background extraction error:", error)
    await updateHypothesis(hypothesisId, {
      extractionStatus: "failed",
      idea: error instanceof Error ? error.message : "Unknown extraction error"
    })
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const parsed = ExtractAndCreateSchema.safeParse(body)
    
    if (!parsed.success) {
      const firstError = parsed.error.issues[0]
      return NextResponse.json(
        { error: firstError.message },
        { status: 400 }
      )
    }

    // Create hypothesis immediately with extracting status
    const hypothesisId = randomUUID()
    const hypothesis = await createHypothesis({
      _id: hypothesisId,
      title: "Extracting from ChatGPT...",
      idea: "Processing ChatGPT conversation. This will update automatically.",
      createdAt: new Date(),
      createdBy: "chatgpt",
      chatGptUrl: parsed.data.url,
      extractionStatus: "extracting"
    })

    // Trigger background processing (don't await)
    processExtractionInBackground(hypothesisId, parsed.data.url).catch(err => {
      console.error("Failed to process extraction in background:", err)
    })

    // Return immediately so user can navigate away
    return NextResponse.json({
      success: true,
      hypothesis,
      message: "Hypothesis created. Extraction is processing in the background."
    }, { status: 201 })

  } catch (error) {
    console.error("ChatGPT extract-and-create error:", error)
    
    if (error instanceof Error) {
      return NextResponse.json(
        { error: error.message || "Failed to create hypothesis from ChatGPT conversation" },
        { status: 500 }
      )
    }

    return NextResponse.json(
      { error: "An unexpected error occurred while creating the hypothesis" },
      { status: 500 }
    )
  }
}

