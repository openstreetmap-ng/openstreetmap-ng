import { roundTo } from "@std/math/round-to"

export const isLongitude = (lon: number) => lon >= -180 && lon <= 180

export const isLatitude = (lat: number) => lat >= -90 && lat <= 90

export const isZoom = (zoom: number) => zoom >= 0 && zoom <= 25

export const beautifyZoom = (zoom: number) =>
    roundTo(zoom, 2, { strategy: "trunc" }).toString()

/** Coordinate precision (decimal places) for a given zoom level */
export const zoomPrecision = (zoom: number) =>
    Math.max(0, Math.ceil(Math.log(zoom | 0) / Math.LN2))

/** Parse "lat, lon" string into [lon, lat], or null if invalid */
export const tryParsePoint = (text: string) => {
    if (!text) return null
    const parts = text.split(",")
    if (parts.length !== 2) return null
    const lat = Number.parseFloat(parts[0].trim())
    const lon = Number.parseFloat(parts[1].trim())
    return isLatitude(lat) && isLongitude(lon) ? ([lon, lat] as const) : null
}
