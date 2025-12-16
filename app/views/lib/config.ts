import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import { WebConfigSchema } from "@lib/proto/shared_pb"
import { memoize } from "@std/cache/memoize"
import {
    _API_URL,
    _ENV,
    _ID_PATH,
    _MAP_QUERY_AREA_MAX_SIZE,
    _NOTE_QUERY_AREA_MAX_SIZE,
    _RAPID_PATH,
    _SENTRY_DSN,
    _SENTRY_TRACES_SAMPLE_RATE,
    _STANDARD_PAGINATION_DISTANCE,
    _STANDARD_PAGINATION_MAX_FULL_PAGES,
    _URLSAFE_BLACKLIST,
    _URLSAFE_BLACKLIST_RE,
    _VERSION,
} from "./config.macro" with { type: "macro" }

export const API_URL = _API_URL
export const ENV = _ENV
export const ID_PATH = _ID_PATH
export const MAP_QUERY_AREA_MAX_SIZE = _MAP_QUERY_AREA_MAX_SIZE
export const NOTE_QUERY_AREA_MAX_SIZE = _NOTE_QUERY_AREA_MAX_SIZE
export const RAPID_PATH = _RAPID_PATH
export const SENTRY_DSN = _SENTRY_DSN
export const SENTRY_TRACES_SAMPLE_RATE = _SENTRY_TRACES_SAMPLE_RATE
export const STANDARD_PAGINATION_DISTANCE = _STANDARD_PAGINATION_DISTANCE
export const STANDARD_PAGINATION_MAX_FULL_PAGES = _STANDARD_PAGINATION_MAX_FULL_PAGES
export const URLSAFE_BLACKLIST = _URLSAFE_BLACKLIST
export const URLSAFE_BLACKLIST_RE = _URLSAFE_BLACKLIST_RE
export const VERSION = _VERSION

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
