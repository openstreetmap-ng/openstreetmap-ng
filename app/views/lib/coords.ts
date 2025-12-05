/**
 * Check if number is a valid longitude
 * @example
 * isLongitude(180)
 * // => true
 */
export const isLongitude = (lon: number): boolean => lon >= -180 && lon <= 180

/**
 * Check if number is a valid latitude
 * @example
 * isLatitude(90)
 * // => true
 */
export const isLatitude = (lat: number): boolean => lat >= -90 && lat <= 90

/**
 * Check if number is a valid zoom level
 * @example
 * isZoom(17)
 * // => true
 */
export const isZoom = (zoom: number): boolean => zoom >= 0 && zoom <= 25

/**
 * Get a zoom level as a string with 2 decimal places
 * @example
 * beautifyZoom(4.4321)
 * // => "4.43"
 */
export const beautifyZoom = (zoom: number): string =>
    (((zoom * 100) | 0) / 100).toString()

/**
 * Compute the coordinate precision for a given zoom level
 * @example
 * zoomPrecision(17)
 * // => 5
 */
export const zoomPrecision = (zoom: number): number =>
    Math.max(0, Math.ceil(Math.log(zoom | 0) / Math.LN2))

/**
 * Parse a simple "lat, lon" string into [lon, lat]. Returns null if invalid.
 * @example
 * tryParsePoint("51.5, -0.1")
 * // => [-0.1, 51.5]
 */
export const tryParsePoint = (text: string): [number, number] | null => {
    if (!text) return null
    const parts = text.split(",")
    if (parts.length !== 2) return null
    const lat = Number.parseFloat(parts[0].trim())
    const lon = Number.parseFloat(parts[1].trim())
    return isLatitude(lat) && isLongitude(lon) ? [lon, lat] : null
}
