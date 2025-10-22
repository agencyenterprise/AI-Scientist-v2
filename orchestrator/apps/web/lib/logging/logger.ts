import pino from "pino"
import { getEnv } from "../config/env"

const env = getEnv()

export const logger = pino({
  level: env.NODE_ENV === "production" ? "info" : "debug",
  base: undefined
})

export function createLogger(context: Record<string, unknown>) {
  return logger.child(context)
}
