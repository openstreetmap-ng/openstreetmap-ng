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
 * Locale hash map
 * @type {object}
 * @example {"en":"f40fd5bd91bde9c9",...}
 */
export const localeHashMap = config.localeHashMap

/**
 * User preferred languages
 * @type {string[]}
 * @example ["en", "pl"]
 */
export const languages = config.languages

/**
 * User preferred primary language
 * @type {string}
 * @example "en"
 */
export const primaryLanguage = languages[0]

/**
 * Optional user home location point (JSON-encoded)
 * @type {number[]|undefined}
 * @example [0, 30]
 */
export const homePoint = config.homePoint

/**
 * Optional user country bounding box in minLon,minLat,maxLon,maxLat format (JSON-encoded)
 * @type {number[]|undefined}
 * @example [14.123, 49.006, 24.150, 54.839]
 */
export const countryBounds = config.countryBounds

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
