import i18next from "i18next"

/**
 * Format distance in meters
 * @param {number} meters Distance in meters
 * @returns {string} Formatted distance
 * @example
 * formatDistance(1100)
 * // => "1.1km"
 */
export const formatDistance = (meters) => {
    // < 1 km
    if (meters < 1000) {
        return i18next.t("javascripts.directions.distance_m", { distance: Math.round(meters) })
    }
    // < 10 km
    if (meters < 10000) {
        return i18next.t("javascripts.directions.distance_km", { distance: (meters / 1000.0).toFixed(1) })
    }
    return i18next.t("javascripts.directions.distance_km", { distance: Math.round(meters / 1000) })
}

/**
 * Format height in meters
 * @param {number} meters Height in meters
 * @returns {string} Formatted height
 * @example
 * formatHeight(200)
 * // => "200m"
 */
export const formatHeight = (meters) => {
    return i18next.t("javascripts.directions.distance_m", { distance: Math.round(meters) })
}

/**
 * Format time in seconds
 * @param {number} seconds Time in seconds
 * @returns {string} Formatted time
 * @example
 * formatTime(3600)
 * // => "1:00"
 */
export const formatTime = (seconds) => {
    // TODO: nice hours and minutes text
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    return `${h}:${m.toString().padStart(2, "0")}`
}
