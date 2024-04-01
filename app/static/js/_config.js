// Global dataset options are defined on <html> tag
const config = JSON.parse(document.documentElement.dataset.config)

// Determine default tracking based on user browser settings
const defaultTracking = navigator.doNotTrack !== "1" && !navigator.globalPrivacyControl

/**
 * API base URL
 * @type {string}
 * @example "https://api.openstreetmap.org"
 */
export const apiUrl = config.apiUrl

/**
 * User primary translation language
 * @type {string}
 * @example "pl"
 */
export const primaryLanguage = document.documentElement.lang

/**
 * Maximum map query area in square degrees
 * @type {number}
 * @example 0.25
 */
export const mapQueryAreaMaxSize = config.mapQueryAreaMaxSize

/**
 * Maximum note query area in square degrees
 * @type {number}
 * @example 25
 */
export const noteQueryAreaMaxSize = config.noteQueryAreaMaxSize

/**
 * Optional user home location point
 * @type {number[]|undefined}
 * @example [0, 30]
 */
export const homePoint = config.homePoint

/**
 * Flag to enable activity tracking
 * @type {boolean}
 * @example false
 */
export const activityTracking = config.activityTracking ?? defaultTracking

/**
 * Flag to enable crash reporting
 * @type {boolean}
 * @example true
 */
export const crashReporting = config.crashReporting ?? defaultTracking
