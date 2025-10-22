export const RUN_STATUSES = [
  "QUEUED",
  "SCHEDULED",
  "STARTING",
  "RUNNING",
  "AUTO_VALIDATING",
  "AWAITING_HUMAN",
  "HUMAN_VALIDATED",
  "FAILED",
  "CANCELED"
] as const

export type RunStatus = (typeof RUN_STATUSES)[number]

export const STAGES = ["Stage_1", "Stage_2", "Stage_3", "Stage_4"] as const

export type StageName = (typeof STAGES)[number]

export const STAGE_DESCRIPTIONS: Record<StageName, string> = {
  Stage_1: "Preliminary Investigation",
  Stage_2: "Baseline Tuning",
  Stage_3: "Research Agenda Execution",
  Stage_4: "Ablation Studies"
}
