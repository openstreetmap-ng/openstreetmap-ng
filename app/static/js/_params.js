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
 * Rapid editor base URL
 * @type {string}
 * @example "https://rapid.openstreetmap.org"
 */
export const rapidUrl = config.rapidUrl

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
// TODO: py, only existing/installed locales

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
