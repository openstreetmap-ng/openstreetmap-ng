import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import { WebConfigSchema } from "./proto/shared_pb"

/** Global dataset options that are defined on <html> tag */
export const config = fromBinary(
    WebConfigSchema,
    base64Decode(document.documentElement.dataset.config),
)
console.info("Application version", config.version)

/** Determine default tracking based on user browser settings */
const defaultTracking =
    navigator.doNotTrack !== "1" && !(navigator as any).globalPrivacyControl

/** Whether to enable activity tracking */
export const activityTracking: boolean =
    config.userConfig?.activityTracking ?? defaultTracking

/** Whether to enable crash reporting */
export const crashReporting: boolean =
    config.sentryConfig &&
    (config.env === "test" || (config.userConfig?.crashReporting ?? defaultTracking))

/**
 * User's primary translation language
 * @example "pl"
 */
export const primaryLanguage: string = document.documentElement.lang

/** Whether user prefers reduced motion */
export const prefersReducedMotion: boolean = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
).matches
