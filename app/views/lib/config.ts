import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import { memoize } from "@lib/memoize"
import { WebConfigSchema } from "@lib/proto/shared_pb"
import {
    _API_URL,
    _ENV,
    _MAP_QUERY_AREA_MAX_SIZE,
    _NOTE_QUERY_AREA_MAX_SIZE,
    _SENTRY_DSN,
    _SENTRY_TRACES_SAMPLE_RATE,
    _URLSAFE_BLACKLIST,
    _VERSION,
} from "./config.macro" with { type: "macro" }
import { getLocaleOptions } from "./locale.macro" with { type: "macro" }

export const API_URL = _API_URL
export const ENV = _ENV
export const MAP_QUERY_AREA_MAX_SIZE = _MAP_QUERY_AREA_MAX_SIZE
export const NOTE_QUERY_AREA_MAX_SIZE = _NOTE_QUERY_AREA_MAX_SIZE
export const SENTRY_DSN = _SENTRY_DSN
export const SENTRY_TRACES_SAMPLE_RATE = _SENTRY_TRACES_SAMPLE_RATE
export const URLSAFE_BLACKLIST = _URLSAFE_BLACKLIST
export const VERSION = _VERSION

export const LOCALE_OPTIONS = getLocaleOptions()

/** Global dataset options that are defined on <html> tag */
export const config = fromBinary(
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
