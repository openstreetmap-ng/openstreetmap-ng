/**
 * Original page title
 * @type {string}
 * @example "OpenStreetMap"
 */
const originalTitle = document.title

/**
 * Get page title with optional prefix
 * @param {string|null} prefix Optional title prefix
 * @returns {string} Page title
 * @example getPageTitle("Export")
 * // => "Export | OpenStreetMap"
 */
export const getPageTitle = (prefix = null) => (prefix ? `${prefix} | ${originalTitle}` : originalTitle)
