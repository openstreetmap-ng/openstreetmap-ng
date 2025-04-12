import i18next from "i18next"
import type { LonLat } from "./map/map-utils"

/**
 * Format distance in meters
 * @example
 * formatDistance(1100)
 * // => "1.1km"
 */
export const formatDistance = (meters: number): string => {
    const km = meters / 1000
    if (km < 1)
        return i18next.t("javascripts.directions.distance_m", {
            distance: Math.round(meters),
        })
    return i18next.t("javascripts.directions.distance_km", {
        distance: km.toFixed(km < 10 ? 1 : 0),
    })
}

/**
 * Format distance in meters, rounded to the two significant digits
 * @example
 * formatDistanceRounded(232)
 * // => "230m"
 */
export const formatDistanceRounded = (meters: number): string => {
    if (meters < 5) return ""
    if (meters < 1500) {
        const precision = meters < 200 ? 10 : 100
        return i18next.t("javascripts.directions.distance_m", {
            distance: Math.round(meters / precision) * precision,
        })
    }
    const digits = meters < 5000 ? 1 : 0
    return i18next.t("javascripts.directions.distance_km", {
        distance: (meters / 1000).toFixed(digits),
    })
}

/**
 * Format height in meters
 * @example
 * formatHeight(200)
 * // => "200m"
 */
export const formatHeight = (meters: number): string => {
    return i18next.t("javascripts.directions.distance_m", {
        distance: Math.round(meters),
    })
}

/**
 * Format time in seconds
 * @example
 * formatTime(3600)
 * // => "1:00"
 */
export const formatTime = (seconds: number): string => {
    // TODO: nice hours and minutes text
    const h = (seconds / 3600) | 0
    const m = ((seconds % 3600) / 60) | 0
    return `${h}:${m.toString().padStart(2, "0")}`
}

/**
 * Format degrees to their correct math representation
 * @example formatDegrees(21.32123)
 * // => "21°19′16″"
 */
export const formatDegrees = (decimalDegree: number): string => {
    const deg = decimalDegree | 0
    const minSec = (decimalDegree - deg) * 60
    const min = minSec | 0
    const sec = ((minSec - min) * 60) | 0

    // Pad single digits with a leading zero
    const degStr = deg < 10 ? `0${deg}` : `${deg}`
    const minStr = min < 10 ? `0${min}` : `${min}`
    const secStr = sec < 10 ? `0${sec}` : `${sec}`
    return `${degStr}°${minStr}′${secStr}″`
}

/**
 * Format [lat, lon] in the geographic coordinate system.
 * @see https://en.wikipedia.org/wiki/Geographic_coordinate_system
 * @example formatCoordinate(21.32123, 35.2134)
 * // => "21°19′16″N 35°12′48″E"
 */
export const formatCoordinate = ({ lon, lat }: LonLat): string => {
    const latDegrees = formatDegrees(lat)
    const lonDegrees = formatDegrees(lon)
    const latDir = lat === 0 ? "" : lat > 0 ? "N" : "S"
    const lonDir = lon === 0 ? "" : lon > 0 ? "E" : "W"
    return `${latDegrees}${latDir} ${lonDegrees}${lonDir}`
}
