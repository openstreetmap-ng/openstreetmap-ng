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
    return i18next.t("javascripts.directions.distance_km", { distance: (meters / 1000.0).toFixed(0) })
}

/**
 * Format distance in meters, that is easier to read but less precise
 * @param {number} meters Distance in meters
 * @returns {string} Formatted distance
 * @example
 * formatSimpleDistance(1100)
 * // => "1.1km"
 */
export const formatSimpleDistance = (meters) => {
    // < 5 m
    if (meters < 5) {
        return ""
    }
    // < 200 m
    if (meters < 200) {
        return i18next.t("javascripts.directions.distance_m", { distance: Math.round(meters / 10) * 10 })
    }
    // < 1500 m
    if (meters < 1500) {
        return i18next.t("javascripts.directions.distance_m", { distance: Math.round(meters / 100) * 100 })
    }
    // < 5 km
    if (meters < 5000) {
        return i18next.t("javascripts.directions.distance_km", { distance: (meters / 1000.0).toFixed(1) })
    }
    return i18next.t("javascripts.directions.distance_km", { distance: (meters / 1000.0).toFixed(0) })
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

/**
 * Format degrees to their correct math representation
 * @param {int} decimalDegree degrees
 * @returns {string}
 * @example formatDegrees(21.32123)
 * // => "21°19′16″"
 */
export const formatDegrees = (decimalDegree) => {
    const degrees = Math.floor(decimalDegree)
    const minutes = Math.floor((decimalDegree - degrees) * 60)
    const seconds = Math.round(((decimalDegree - degrees) * 60 - minutes) * 60)

    // Pad single digits with a leading zero
    const formattedDegrees = degrees < 10 ? `0${degrees}` : `${degrees}`
    const formattedSeconds = seconds < 10 ? `0${seconds}` : `${seconds}`
    const formattedMinutes = minutes < 10 ? `0${minutes}` : `${minutes}`

    return `${formattedDegrees}°${formattedMinutes}′${formattedSeconds}″`
}

/**
 * Format lat lon in cordinate system. See https://en.wikipedia.org/wiki/Geographic_coordinate_system
 * @param {L.LatLng} pos position on map
 * @returns {string}
 * @example formatLatLon({lat: 21.32123, 35.2134})
 * // => "21°19′16″N, 35°12′48″E"
 */

export const formatLatLon = (latLng) => {
    const lat = formatDegrees(latLng.lat)
    const lon = formatDegrees(latLng.lng)
    const latDir = latLng.lat === 0 ? "" : latLng.lat > 0 ? "N" : "S"
    const lonDir = latLng.lat === 0 ? "" : latLng.lat > 0 ? "E" : "W"
    return `${lat}${latDir} ${lon}${lonDir}`
}
