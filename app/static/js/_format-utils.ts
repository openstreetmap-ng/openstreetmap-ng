import i18next from "i18next"
import type { LonLat } from "./leaflet/_map-utils"

/**
 * Format distance in meters
 * @example
 * formatDistance(1100)
 * // => "1.1km"
 */
export const formatDistance = (meters: number): string => {
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
 * Format distance in meters, rounded to the two significant digits
 * @example
 * formatDistanceRounded(232)
 * // => "230m"
 */
export const formatDistanceRounded = (meters: number): string => {
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
 * @example
 * formatHeight(200)
 * // => "200m"
 */
export const formatHeight = (meters: number): string => {
    return i18next.t("javascripts.directions.distance_m", { distance: Math.round(meters) })
}

/**
 * Format time in seconds
 * @example
 * formatTime(3600)
 * // => "1:00"
 */
export const formatTime = (seconds: number): string => {
    // TODO: nice hours and minutes text
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    return `${h}:${m.toString().padStart(2, "0")}`
}

/**
 * Format degrees to their correct math representation
 * @example formatDegrees(21.32123)
 * // => "21°19′16″"
 */
export const formatDegrees = (decimalDegree: number): string => {
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
 * Format [lat, lon] in the geographic coordinate system.
 * @see https://en.wikipedia.org/wiki/Geographic_coordinate_system
 * @example formatCoordinate(21.32123, 35.2134)
 * // => "21°19′16″N, 35°12′48″E"
 */

export const formatCoordinate = ({ lon, lat }: LonLat): string => {
    const latDegrees = formatDegrees(lat)
    const lonDegrees = formatDegrees(lon)
    const latDir = lat === 0 ? "" : lat > 0 ? "N" : "S"
    const lonDir = lon === 0 ? "" : lon > 0 ? "E" : "W"
    return `${latDegrees}${latDir} ${lonDegrees}${lonDir}`
}
