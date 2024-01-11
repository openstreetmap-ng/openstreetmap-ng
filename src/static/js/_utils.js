// Check if number is a valid longitude
export const isLongitude = (lon) => lon >= -180 && lon <= 180

// Check if number is a valid latitude
export const isLatitude = (lat) => lat >= -90 && lat <= 90

// Check if number is a valid zoom level
export const isZoom = (zoom) => zoom >= 0 && zoom <= 25

// Compute the coordinate precision for a given zoom level
export const zoomPrecision = (zoom) => Math.max(0, Math.ceil(Math.log(zoom) / Math.LN2))

// Throttle a function to only be called once every `delay` milliseconds
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
