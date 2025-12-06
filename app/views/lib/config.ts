import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import { memoize } from "@lib/memoize"
import { WebConfigSchema } from "@lib/proto/shared_pb"

/** Global dataset options that are defined on <html> tag */
export const config = fromBinary(
    WebConfigSchema,
    base64Decode(document.documentElement.dataset.config!),
)
console.info("Application version", config.version)

/** Determine default tracking based on user browser settings */
const DEFAULT_TRACKING =
    navigator.doNotTrack !== "1" && !(navigator as any).globalPrivacyControl

/** Whether to enable activity tracking */
export const activityTracking = config.userConfig?.activityTracking ?? DEFAULT_TRACKING

/** Check if crash reporting is enabled */
export const isCrashReportingEnabled = (
    cfg: typeof config,
): cfg is typeof config & { sentryConfig: NonNullable<typeof config.sentryConfig> } =>
    Boolean(
        cfg.sentryConfig &&
            (cfg.env === "test" ||
                (cfg.userConfig?.crashReporting ?? DEFAULT_TRACKING)),
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
