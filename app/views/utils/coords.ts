import { clamp } from "@std/math/clamp"
import { modulo } from "@std/math/modulo"
import { roundTo } from "@std/math/round-to"
import type { LngLatLike } from "maplibre-gl"

export const MAX_MERCATOR_LATITUDE = 85.05112878

export const isLongitude = (lon: number | undefined | null): lon is number =>
  typeof lon === "number" && lon >= -180 && lon <= 180

export const isLatitude = (lat: number | undefined | null): lat is number =>
  typeof lat === "number" &&
  lat >= -MAX_MERCATOR_LATITUDE &&
  lat <= MAX_MERCATOR_LATITUDE

export const isZoom = (zoom: number | undefined | null): zoom is number =>
  typeof zoom === "number" && zoom >= 0 && zoom <= 25

export const wrapLongitude = (lon: number) => modulo(lon + 180, 360) - 180

export const clampLatitude = (lat: number) =>
  clamp(lat, -MAX_MERCATOR_LATITUDE, MAX_MERCATOR_LATITUDE)

export const beautifyZoom = (zoom: number) =>
  roundTo(zoom, 2, { strategy: "trunc" }).toString()

/** Coordinate precision (decimal places) for a given zoom level */
export const zoomPrecision = (zoom: number) =>
  Math.max(0, Math.ceil(Math.log2(Math.round(zoom))))

/** Parse "lat, lon" string into [lon, lat], or null if invalid */
export const tryParsePoint = (text: string | undefined | null) => {
  if (!text) return null
  const parts = text.split(",")
  if (parts.length !== 2) return null
  return tryParseLonLat(parts[1]!.trim(), parts[0]!.trim())
}

export const tryParseLonLat = (
  lonText: string | undefined | null,
  latText: string | undefined | null,
) => {
  const lon = Number.parseFloat(lonText ?? "")
  const lat = Number.parseFloat(latText ?? "")
  return isLongitude(lon) && isLatitude(lat) ? ([lon, lat] as const) : null
}

export const tryParseLonLatZoom = (
  lonText: string | undefined | null,
  latText: string | undefined | null,
  zoomText: string | undefined | null,
) => {
  const location = tryParseLonLat(lonText, latText)
  if (!location) return null
  const zoom = Number.parseFloat(zoomText ?? "")
  return isZoom(zoom) ? { lon: location[0], lat: location[1], zoom } : null
}

export const formatPoint = (point: LngLatLike, precision: number) => {
  let lon: number
  let lat: number

  if (Array.isArray(point)) {
    ;[lon, lat] = point
  } else {
    lon = "lon" in point ? point.lon : point.lng
    lat = point.lat
  }

  return `${lat.toFixed(precision)}, ${lon.toFixed(precision)}`
}
