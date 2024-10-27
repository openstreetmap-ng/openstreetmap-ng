/**
 * Original page title
 * @example "OpenStreetMap"
 */
const originalTitle: string = document.title

/**
 * Get page title with optional prefix
 * @example getPageTitle("Export")
 * // => "Export | OpenStreetMap"
 */
export const getPageTitle = (prefix?: string): string => (prefix ? `${prefix} | ${originalTitle}` : originalTitle)
