import type { Bounds } from "@lib/types"
import { clamp } from "@std/math/clamp"
import {
  LngLatBounds,
  type FitBoundsOptions as MaplibreFitBoundsOptions,
  type Map as MaplibreMap,
} from "maplibre-gl"

/** Get the bounds area in square degrees */
export const getLngLatBoundsSize = (bounds: LngLatBounds) => {
  const [[minLon, minLat], [maxLon, maxLat]] = bounds.adjustAntiMeridian().toArray()
  return (maxLon - minLon) * (maxLat - minLat)
}

export const getLngLatBoundsIntersection = (
  bounds1: LngLatBounds,
  bounds2: LngLatBounds,
) => {
  const [[minLon1, minLat1], [maxLon1, maxLat1]] = bounds1
    .adjustAntiMeridian()
    .toArray()
  const [[minLon2, minLat2], [maxLon2, maxLat2]] = bounds2
    .adjustAntiMeridian()
    .toArray()

  const minLat = Math.max(minLat1, minLat2)
  const maxLat = Math.min(maxLat1, maxLat2)
  const minLon = Math.max(minLon1, minLon2)
  const maxLon = Math.min(maxLon1, maxLon2)

  // Return zero-sized bounds if no intersection
  if (minLat > maxLat || minLon > maxLon) {
    return new LngLatBounds([minLon1, minLat1, minLon1, minLat1])
  }

  return new LngLatBounds([minLon, minLat, maxLon, maxLat])
}

export const checkLngLatBoundsIntersection = (
  bounds1: LngLatBounds,
  bounds2: LngLatBounds,
) => {
  const [[minLon1, minLat1], [maxLon1, maxLat1]] = bounds1
    .adjustAntiMeridian()
    .toArray()
  const [[minLon2, minLat2], [maxLon2, maxLat2]] = bounds2
    .adjustAntiMeridian()
    .toArray()

  return !(
    minLat1 > maxLat2 ||
    maxLat1 < minLat2 ||
    minLon1 > maxLon2 ||
    maxLon1 < minLon2
  )
}

export const lngLatBoundsEqual = (
  bounds1: LngLatBounds | null | undefined,
  bounds2: LngLatBounds | null | undefined,
) => {
  if (!(bounds1 || bounds2)) return true
  if (!(bounds1 && bounds2)) return false
  const [[minLon1, minLat1], [maxLon1, maxLat1]] = bounds1
    .adjustAntiMeridian()
    .toArray()
  const [[minLon2, minLat2], [maxLon2, maxLat2]] = bounds2
    .adjustAntiMeridian()
    .toArray()
  return (
    minLon1 === minLon2 &&
    minLat1 === minLat2 &&
    maxLon1 === maxLon2 &&
    maxLat1 === maxLat2
  )
}

/** Pad bounds to grow/shrink them */
export const padLngLatBounds = (bounds: LngLatBounds, padding?: number) => {
  if (!padding) return bounds
  const [[minLon, minLat], [maxLon, maxLat]] = bounds.adjustAntiMeridian().toArray()
  const paddingX = padding * (maxLon - minLon)
  const paddingY = padding * (maxLat - minLat)
  return new LngLatBounds([
    minLon - paddingX,
    clamp(minLat - paddingY, -85, 85),
    maxLon + paddingX,
    clamp(maxLat + paddingY, -85, 85),
  ])
}

/** Make bounds minimum size to make them easier to click */
export const makeBoundsMinimumSize = (
  map: MaplibreMap,
  bounds: Bounds,
  minSizePx = 20,
) => {
  const [minLon, minLat, maxLon, maxLat] = bounds
  const mapBottomLeft = map.project([minLon, minLat])
  const mapTopRight = map.project([maxLon, maxLat])
  const width = mapTopRight.x - mapBottomLeft.x
  const height = mapBottomLeft.y - mapTopRight.y

  if (width < minSizePx) {
    const diff = minSizePx - width
    mapBottomLeft.x -= diff / 2
    mapTopRight.x += diff / 2
  }

  if (height < minSizePx) {
    const diff = minSizePx - height
    mapBottomLeft.y += diff / 2
    mapTopRight.y -= diff / 2
  }

  const lngLatBottomLeft = map.unproject(mapBottomLeft)
  const lngLatTopRight = map.unproject(mapTopRight)
  return [
    lngLatBottomLeft.lng,
    lngLatBottomLeft.lat,
    lngLatTopRight.lng,
    lngLatTopRight.lat,
  ] as Bounds
}

export interface FitBoundsOptions {
  /** Amount of padding to add to the bounds @default 0.2 */
  padBounds?: number | undefined
  /** Maximum zoom level to focus on @default 18 */
  maxZoom?: number | undefined
  /** Whether to perform intersection check instead of containment @default false */
  intersects?: boolean | undefined
  /** Minimum proportion of bounds to map to trigger fit @default 0.00035 */
  minProportion?: number | undefined
  /** Whether to animate the fit @default false */
  animate?: boolean | undefined
}

export const fitBoundsIfNeeded = (
  map: MaplibreMap,
  bounds: LngLatBounds,
  opts?: FitBoundsOptions,
) => {
  const padBounds = opts?.padBounds ?? 0.2
  const maxZoom = opts?.maxZoom ?? 18
  const intersects = opts?.intersects ?? false
  const minProportion = opts?.minProportion ?? 0.00035
  const animate = opts?.animate ?? false

  const mapBounds = map.getBounds().adjustAntiMeridian()
  const boundsAdjusted = bounds.adjustAntiMeridian()
  const boundsPadded = padLngLatBounds(boundsAdjusted, padBounds)

  const currentZoom = map.getZoom()
  const fitMaxZoom = Math.max(currentZoom, maxZoom)

  const maplibreOpts: MaplibreFitBoundsOptions = {
    maxZoom: fitMaxZoom,
    animate,
  }

  const isOffscreen = intersects
    ? !checkLngLatBoundsIntersection(mapBounds, boundsPadded)
    : !(
        mapBounds.contains(boundsPadded.getSouthWest()) &&
        mapBounds.contains(boundsPadded.getNorthEast())
      )

  if (isOffscreen) {
    map.fitBounds(boundsPadded, maplibreOpts)
    return { reason: "offscreen", fitMaxZoom }
  }

  if (minProportion > 0 && fitMaxZoom > currentZoom) {
    const boundsSize = getLngLatBoundsSize(boundsAdjusted)
    const mapBoundsSize = getLngLatBoundsSize(mapBounds)
    const proportion = boundsSize / mapBoundsSize
    if (proportion > 0 && proportion < minProportion) {
      map.fitBounds(boundsPadded, maplibreOpts)
      return { reason: "small", fitMaxZoom }
    }
  }

  return null
}

export const unionBounds = (left: Bounds | null | undefined, right: Bounds) =>
  left
    ? ([
        Math.min(left[0], right[0]),
        Math.min(left[1], right[1]),
        Math.max(left[2], right[2]),
        Math.max(left[3], right[3]),
      ] as Bounds)
    : right
