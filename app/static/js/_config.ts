import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import type { LonLat } from "./leaflet/_map-utils"
import { WebConfigSchema } from "./proto/shared_pb"

/** Global dataset options that are defined on <html> tag */
const config = fromBinary(WebConfigSchema, base64Decode(document.documentElement.dataset.config))

/** Determine default tracking based on user browser settings */
const defaultTracking = navigator.doNotTrack !== "1" && !(navigator as any).globalPrivacyControl

/**
 * API base URL
 * @example "https://api.openstreetmap.org"
 */
export const apiUrl: string = config.apiUrl

/**
 * User's primary translation language
 * @example "pl"
 */
export const primaryLanguage: string = document.documentElement.lang

/**
 * Maximum map query area in square degrees
 * @example 0.25
 */
export const mapQueryAreaMaxSize: number = config.mapQueryAreaMaxSize

/**
 * Maximum note query area in square degrees
 * @example 25
 */
export const noteQueryAreaMaxSize: number = config.noteQueryAreaMaxSize

/**
 * Optional user home location point
 * @example [0, 30]
 */
export const homePoint: LonLat | undefined = config.userConfig?.homePoint

/** Whether to enable activity tracking */
export const activityTracking: boolean = config.userConfig?.activityTracking ?? defaultTracking

/** Whether to enable crash reporting */
export const crashReporting: boolean = config.userConfig?.crashReporting ?? defaultTracking
