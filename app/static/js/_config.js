// Global dataset options are defined on <html> tag
const config = JSON.parse(document.documentElement.dataset.config)

/**
 * API base URL
 * @type {string}
 * @example "https://api.openstreetmap.org"
 */
export const apiUrl = config.apiUrl

/**
 * ID editor base URL
 * @type {string}
 * @example "https://id.openstreetmap.org"
 */
export const idUrl = config.idUrl

/**
 * ID editor version
 * @type {string}
 * @example "abc123"
 */
export const idVersion = config.idVersion

/**
 * Rapid editor base URL
 * @type {string}
 * @example "https://rapid.openstreetmap.org"
 */
export const rapidUrl = config.rapidUrl

/**
 * Rapid editor version
 * @type {string}
 * @example "abc123"
 */
export const rapidVersion = config.rapidVersion

/**
 * User translation languages
 * @type {string[]}
 * @example ["en", "pl"]
 */
export const languages = config.languages

/**
 * User primary translation language
 * @type {string}
 * @example "en"
 */
export const primaryLanguage = languages[0]

/**
 * Optional user home location point
 * @type {number[]|null}
 * @example [0, 30]
 */
export const homePoint = config.homePoint

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
