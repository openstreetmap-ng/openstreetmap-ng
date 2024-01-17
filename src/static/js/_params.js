// Global dataset options are defined on <html> tag
const params = document.documentElement.dataset

/**
 * API base URL
 * @type {string}
 * @example "https://api.openstreetmap.org"
 */
export const apiUrl = params.apiUrl

/**
 * ID editor base URL
 * @type {string}
 * @example "https://id.openstreetmap.org"
 */
export const idUrl = params.idUrl

/**
 * Rapid editor base URL
 * @type {string}
 * @example "https://rapid.openstreetmap.org"
 */
export const rapidUrl = params.rapidUrl

/**
 * User preferred languages
 * @type {string[]}
 * @example ["en", "pl"]
 */
export const languages = JSON.parse(params.languages)

/**
 * User preferred primary language
 * @type {string}
 * @example "en"
 */
export const primaryLanguage = languages[0]
// TODO: py, only existing/installed locales

/**
 * Optional user home location point (JSON-encoded)
 * @type {string|undefined}
 * @example "[0, 30]"
 */
export const homePoint = params.homePoint

/**
 * Optional user country bounding box in minLon,minLat,maxLon,maxLat format (JSON-encoded)
 * @type {string|undefined}
 * @example "[14.123, 49.006, 24.150, 54.839]"
 */
export const countryBounds = params.countryBounds

// TODO: perhaps useful globally?
// Maximum map query area in square degrees
// export const mapQueryAreaMaxSize = params.mapQueryAreaMaxSize

// Maximum note query area in square degrees
// export const noteQueryAreaMaxSize = params.noteQueryAreaMaxSize
