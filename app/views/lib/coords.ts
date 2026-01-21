import { clamp } from "@std/math/clamp"
import { modulo } from "@std/math/modulo"
import { roundTo } from "@std/math/round-to"
import type { LngLatLike } from "maplibre-gl"

export const MAX_MERCATOR_LATITUDE = 85.05112878

export const isLongitude = (lon: number) => lon >= -180 && lon <= 180

export const isLatitude = (lat: number) =>
  lat >= -MAX_MERCATOR_LATITUDE && lat <= MAX_MERCATOR_LATITUDE

export const isZoom = (zoom: number) => zoom >= 0 && zoom <= 25

export const wrapLongitude = (lon: number) => modulo(lon + 180, 360) - 180

export const clampLatitude = (lat: number) =>
  clamp(lat, -MAX_MERCATOR_LATITUDE, MAX_MERCATOR_LATITUDE)

export const beautifyZoom = (zoom: number) =>
  roundTo(zoom, 2, { strategy: "trunc" }).toString()

/** Coordinate precision (decimal places) for a given zoom level */
export const zoomPrecision = (zoom: number) =>
  Math.max(0, Math.ceil(Math.log(Math.round(zoom)) / Math.LN2))

/** Parse "lat, lon" string into [lon, lat], or null if invalid */
export const tryParsePoint = (text: string | undefined | null) => {
  if (!text) return null
  const parts = text.split(",")
  if (parts.length !== 2) return null
  const lat = Number.parseFloat(parts[0].trim())
  const lon = Number.parseFloat(parts[1].trim())
  return isLatitude(lat) && isLongitude(lon) ? ([lon, lat] as const) : null
}

export const formatPoint = (point: LngLatLike, precision: number) => {
  let lon: number
  let lat: number

  if (Array.isArray(point)) {
    ;[lon, lat] = point
  } else if ("lon" in point) {
    lon = point.lon
    lat = point.lat
  } else {
    lon = point.lng
    lat = point.lat
  }

  return `${lat.toFixed(precision)}, ${lon.toFixed(precision)}`
}
