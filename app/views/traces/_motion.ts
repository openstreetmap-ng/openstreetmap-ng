import { prefersReducedMotion } from "@lib/config"

const REDUCED_MOTION_DURATION_FACTOR = 4

export const traceMotionDuration = (duration: number) =>
  prefersReducedMotion() ? duration * REDUCED_MOTION_DURATION_FACTOR : duration
