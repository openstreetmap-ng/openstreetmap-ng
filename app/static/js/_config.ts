// Global dataset options are defined on <html> tag
const config = JSON.parse(document.documentElement.dataset.config)

// Determine default tracking based on user browser settings
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
export const homePoint: [number, number] | undefined = config.homePoint

/**
 * Whether to enable activity tracking
 * @example false
 */
export const activityTracking: boolean = config.activityTracking ?? defaultTracking

/**
 * Whether to enable crash reporting
 * @example true
 */
export const crashReporting: boolean = config.crashReporting ?? defaultTracking
