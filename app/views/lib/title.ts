/**
 * Original page title
 * @example "OpenStreetMap"
 */
const originalTitle = document.title

/**
 * Set page title with optional prefix
 * @example setPageTitle("Export")
 * // => "Export | OpenStreetMap"
 */
export const setPageTitle = (prefix?: string) => {
    document.title = prefix ? `${prefix} | ${originalTitle}` : originalTitle
}
