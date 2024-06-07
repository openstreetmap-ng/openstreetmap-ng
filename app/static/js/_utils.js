/**
 * Check if number is a valid longitude
 * @param {number} lon Longitude
 * @returns {boolean} Whether the number is a valid longitude
 * @example
 * isLongitude(180)
 * // => true
 */
export const isLongitude = (lon) => lon >= -180 && lon <= 180

/**
 * Check if number is a valid latitude
 * @param {number} lat Latitude
 * @returns {boolean} Whether the number is a valid latitude
 * @example
 * isLatitude(90)
 * // => true
 */
export const isLatitude = (lat) => lat >= -90 && lat <= 90

/**
 * Check if number is a valid zoom level
 * @param {number} zoom Zoom level
 * @returns {boolean} Whether the number is a valid zoom level
 * @example
 * isZoom(17)
 * // => true
 */
export const isZoom = (zoom) => zoom >= 0 && zoom <= 25

/**
 * Compute the coordinate precision for a given zoom level
 * @param {number} zoom Zoom level
 * @returns {number} Coordinate precision
 * @example
 * zoomPrecision(17)
 * // => 5
 */
export const zoomPrecision = (zoom) => Math.max(0, Math.ceil(Math.log(zoom) / Math.LN2))

/**
 * Compute the modulo of a number, supporting negative numbers
 * @param {number} n Number
 * @param {number} m Modulo
 * @returns {number} Modulo result
 * @example
 * mod(-1, 3)
 * // => 2
 */
export const mod = (n, m) => ((n % m) + m) % m

/**
 * Throttle a function to only be called at most once per delay
 * @param {function} func Function to throttle
 * @param {number} delay Minimum delay between calls
 * @returns {function} Throttled function
 * @example
 * throttle(() => console.log("Hello"), 1000)
 */
export const throttle = (func, delay) => {
    let lastCalled = 0
    let timeoutId = null

    return (...args) => {
        if (timeoutId) clearTimeout(timeoutId)
        const now = performance.now()
        const timeElapsed = now - lastCalled
        const timeLeft = delay - timeElapsed

        if (timeLeft <= 0) {
            lastCalled = now
            func(...args)
        } else {
            timeoutId = setTimeout(() => {
                lastCalled = performance.now()
                func(...args)
            }, timeLeft)
        }
    }
}

// This is currently not possible with out i18n translations
// as we don't distinguish between en, en-GB, en-US, etc.
// Perhaps, it could be configured in the settings?
// For now, don't support imperial units.
// Also, such simple startsWith check is bug-prone:
// export const isMetricUnit = !(navigator.language.startsWith("en-US") || navigator.language.startsWith("my"))
export const isMetricUnit = true

/**
 * Check if the given href is the current page
 * @param {string} href Href
 * @returns {boolean}
 */
export const isHrefCurrentPage = (href) => {
    const hrefPathname = new URL(href).pathname
    const locationPathname = location.pathname
    return hrefPathname === locationPathname || `${hrefPathname}/` === locationPathname
}

/**
 * Get the current unix timestamp
 * @returns {number} Unix timestamp
 * @example
 * getUnixTimestamp()
 * // => 1717761123
 */
export const getUnixTimestamp = () => Math.floor(Date.now() / 1000)
