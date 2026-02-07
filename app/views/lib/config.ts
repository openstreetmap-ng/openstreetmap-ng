import { base64Decode } from "@bufbuild/protobuf/wire"
import { WebConfigSchema } from "@lib/proto/shared_pb"
import { fromBinaryValid } from "@lib/rpc"
import { memoize } from "@std/cache/memoize"
import { ENV, SENTRY_DSN, VERSION } from "./config.macro" with { type: "macro" }

export * from "./config.macro" with { type: "macro" }

const BOOTSTRAP_BREAKPOINTS = {
  xs: 0,
  sm: 576,
  md: 768,
  lg: 992,
  xl: 1200,
  xxl: 1400,
} as const

const BOOTSTRAP_BREAKPOINT_ORDER = Object.keys(
  BOOTSTRAP_BREAKPOINTS,
) as BootstrapBreakpoint[]

type BootstrapBreakpoint = keyof typeof BOOTSTRAP_BREAKPOINTS

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

const maxWidthQuery = (breakpoint: BootstrapBreakpoint) => {
  const index = BOOTSTRAP_BREAKPOINT_ORDER.indexOf(breakpoint)
  const next = BOOTSTRAP_BREAKPOINT_ORDER[index + 1]
  if (!next) return null

  // Match Bootstrap media-breakpoint-down() behavior: next breakpoint - 0.02px.
  const maxWidth = BOOTSTRAP_BREAKPOINTS[next] - 0.02
  return `(max-width: ${maxWidth.toFixed(2)}px)`
}

const minWidthQuery = (breakpoint: BootstrapBreakpoint) =>
  `(min-width: ${BOOTSTRAP_BREAKPOINTS[breakpoint]}px)`

/** Whether viewport width is at or above the breakpoint */
export const isBreakpointUp = (breakpoint: BootstrapBreakpoint) =>
  window.matchMedia(minWidthQuery(breakpoint)).matches

/** Whether viewport width is at or below the breakpoint */
export const isBreakpointDown = (breakpoint: BootstrapBreakpoint) => {
  const query = maxWidthQuery(breakpoint)
  return query ? window.matchMedia(query).matches : true
}

/**
 * Whether viewport width is between two breakpoints.
 * When only one breakpoint is provided, it matches exactly that breakpoint range.
 */
export const isBreakpointBetween = (
  breakpointFrom: BootstrapBreakpoint,
  breakpointTo: BootstrapBreakpoint = breakpointFrom,
) => {
  const minQuery = minWidthQuery(breakpointFrom)
  const maxQuery = maxWidthQuery(breakpointTo)
  return window.matchMedia(maxQuery ? `${minQuery} and ${maxQuery}` : minQuery).matches
}

/** Whether user prefers reduced motion */
export const prefersReducedMotion = memoize(
  () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
)
