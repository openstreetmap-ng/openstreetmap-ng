import { base64Decode } from "@bufbuild/protobuf/wire"
import { WebConfigSchema } from "@lib/proto/shared_pb"
import { fromBinaryValid } from "@lib/rpc"
import { memoize } from "@std/cache/memoize"
import { ENV, SENTRY_DSN, VERSION } from "./config.macro" with { type: "macro" }
export * from "./config.macro" with { type: "macro" }

/** Global dataset options that are defined on <html> tag */
export const config = fromBinaryValid(
  WebConfigSchema,
  base64Decode(document.documentElement.dataset.config!),
)
console.info("Application version", VERSION)

/** Determine default tracking based on user browser settings */
const DEFAULT_TRACKING =
  navigator.doNotTrack !== "1" && !(navigator as any).globalPrivacyControl

/** Whether to enable activity tracking */
export const activityTracking = config.userConfig?.activityTracking ?? DEFAULT_TRACKING

/** Check if crash reporting is enabled */
export const isCrashReportingEnabled = (cfg: typeof config) =>
  Boolean(
    SENTRY_DSN &&
      (ENV === "test" || (cfg.userConfig?.crashReporting ?? DEFAULT_TRACKING)),
  )

export const isLoggedIn = Boolean(config.userConfig)
export const isModerator =
  isLoggedIn && config.userConfig!.reportsCountModerator !== undefined
export const isAdministrator =
  isLoggedIn && config.userConfig!.reportsCountAdministrator !== undefined

/**
 * User's primary translation language
 * @example "pl"
 */
export const primaryLanguage = document.documentElement.lang

/** Whether user is on a mobile device */
export const isMobile = memoize(() => window.innerWidth <= 1024)

/** Whether user prefers reduced motion */
export const prefersReducedMotion = memoize(
  () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
)
