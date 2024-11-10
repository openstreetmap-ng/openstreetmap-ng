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
 * Compute the coordinate precision for a given zoom level
 * @example
 * zoomPrecision(17)
 * // => 5
 */
export const zoomPrecision = (zoom: number): number => Math.max(0, Math.ceil(Math.log(zoom) / Math.LN2))

/**
 * Compute the modulo of a number, supporting negative numbers
 * @example
 * mod(-1, 3)
 * // => 2
 */
export const mod = (n: number, m: number): number => ((n % m) + m) % m

/**
 * Throttle a function to only be called at most once per delay
 * @example
 * throttle(() => console.log("Hello"), 1000)
 */
export const throttle = <T extends any[]>(func: (...args: T) => void, delay: number): ((...args: T) => void) => {
    let lastCalled = 0
    let timeout: ReturnType<typeof setTimeout> | null = null

    return (...args) => {
        if (timeout) clearTimeout(timeout)
        const now = performance.now()
        const timeElapsed = now - lastCalled
        const timeLeft = delay - timeElapsed

        if (timeLeft <= 0) {
            lastCalled = now
            func(...args)
        } else {
            timeout = setTimeout(() => {
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

/** Check if the given href is the current page */
export const isHrefCurrentPage = (href: string): boolean => {
    const hrefPathname = new URL(href).pathname
    const locationPathname = location.pathname
    return hrefPathname === locationPathname || `${hrefPathname}/` === locationPathname
}

/**
 * Get the current unix timestamp
 * @example
 * getUnixTimestamp()
 * // => 1717761123
 */
export const getUnixTimestamp = (): number => Math.floor(Date.now() / 1000)

/**
 * Create a Python-like range of numbers
 * @example
 * range(1, 5)
 * // => [1, 2, 3, 4]
 */
export const range = (start: number, stop: number, step = 1): number[] => {
    const result: number[] = []
    for (let i = start; i < stop; i += step) result.push(i)
    return result
}

/**
 * Backwards-compatible requestAnimationFrame function
 */
export const requestAnimationFramePolyfill: (callback: FrameRequestCallback) => number =
    window.requestAnimationFrame || ((callback) => window.setTimeout(() => callback(performance.now()), 30))
