import { describe, expect, it, vi } from "vitest"

const mockCreate = vi.fn()
const mockGet = vi.fn()
const mockFindRun = vi.fn()

vi.mock("../repos/paperAnalyses.repo", () => ({
  createPaperAnalysis: mockCreate,
  getPaperAnalysisByRunId: mockGet
}))

vi.mock("../repos/runs.repo", () => ({
  findRunById: mockFindRun
}))

describe("analysis.service", () => {
  it("generates and persists analysis", async () => {
    const { generatePaperAnalysis } = await import("./analysis.service")
    mockFindRun.mockResolvedValueOnce({
      _id: "run",
      hypothesisId: "hypo",
      status: "RUNNING",
      createdAt: new Date(),
      updatedAt: new Date()
    })
    mockGet.mockResolvedValueOnce(null)
    mockCreate.mockImplementation(async (doc) => doc)

    const result = await generatePaperAnalysis(
      {
        runId: "run",
        paperId: "paper",
        paperContent: "A".repeat(200)
      },
      {
        async generateQuantitative() {
          return {
            model: "gpt-quant",
            result: {
              quality: { score: 8 },
              overallScore: 8
            }
          }
        },
        async generateQualitative() {
          return {
            model: "gpt-qual",
            result: {
              tradeoffsMade: {
                example: "tradeoff"
              }
            }
          }
        }
      }
    )

    expect(result.models.quantitative).toBe("gpt-quant")
    expect(result.quantitative.overallScore).toBe(8)
    expect(mockCreate).toHaveBeenCalled()
  })

  it("returns cached analysis when it exists", async () => {
    const { generatePaperAnalysis } = await import("./analysis.service")
    mockFindRun.mockResolvedValue({
      _id: "run",
      hypothesisId: "hypo",
      status: "RUNNING",
      createdAt: new Date(),
      updatedAt: new Date()
    })
    mockGet.mockResolvedValueOnce({
      _id: "analysis-id",
      runId: "run"
    })

    const existing = await generatePaperAnalysis(
      {
        runId: "run",
        paperId: "paper",
        paperContent: "A".repeat(200)
      },
      {
        generateQuantitative: vi.fn(),
        generateQualitative: vi.fn()
      } as never
    )

    expect(existing).toEqual({ _id: "analysis-id", runId: "run" })
    expect(mockCreate).not.toHaveBeenCalled()
  })
})
