// Global dataset options are defined on <html> tag
const params = document.documentElement.dataset

/**
 * API base URL
 * @type {string}
 * @example "https://api.openstreetmap.org"
 */
export const apiUrl = params.apiUrl

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
 * User home location point (JSON-encoded)
 * @type {string}
 * @example "[0, 30]"
 */
export const homePoint = params.homePoint

// TODO: perhaps useful globally?
// Maximum map query area in square degrees
// export const mapQueryAreaMaxSize = params.mapQueryAreaMaxSize

// Maximum note query area in square degrees
// export const noteQueryAreaMaxSize = params.noteQueryAreaMaxSize
