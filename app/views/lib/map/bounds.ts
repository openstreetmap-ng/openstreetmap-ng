import type { Bounds } from "@lib/types"
import { clamp } from "@std/math/clamp"
import {
  LngLatBounds,
  type FitBoundsOptions as MaplibreFitBoundsOptions,
  type Map as MaplibreMap,
} from "maplibre-gl"

/** Get the bounds area in square degrees */
export const boundsSize = (bounds: LngLatBounds) => {
  const [[minLon, minLat], [maxLon, maxLat]] = bounds.adjustAntiMeridian().toArray()
  return (maxLon - minLon) * (maxLat - minLat)
}

export function boundsToBounds(bounds: LngLatBounds): Bounds
export function boundsToBounds(bounds: Bounds): LngLatBounds
export function boundsToBounds(bounds: LngLatBounds | Bounds) {
  if (bounds instanceof LngLatBounds) {
    const [[minLon, minLat], [maxLon, maxLat]] = bounds.adjustAntiMeridian().toArray()
    return [minLon, minLat, maxLon, maxLat] satisfies Bounds
  }

  return new LngLatBounds(bounds)
}

export const boundsToString = (bounds: LngLatBounds | Bounds) => {
  let minLon: number, minLat: number, maxLon: number, maxLat: number
  if (bounds instanceof LngLatBounds) {
    ;[[minLon, minLat], [maxLon, maxLat]] = bounds.adjustAntiMeridian().toArray()
  } else {
    ;[minLon, minLat, maxLon, maxLat] = bounds
  }
  return `${minLon},${minLat},${maxLon},${maxLat}`
}

export const boundsIntersection = (
  bounds1: LngLatBounds,
  bounds2: LngLatBounds,
  eps = 1e-7,
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

  // Treat small intersections as empty.
  if (minLat >= maxLat - eps || minLon >= maxLon - eps) {
    return new LngLatBounds([minLon1, minLat1, minLon1, minLat1])
  }

  return new LngLatBounds([minLon, minLat, maxLon, maxLat])
}

export const boundsIntersect = (
  bounds1: LngLatBounds,
  bounds2: LngLatBounds,
  eps = 1e-7,
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
  return minLat < maxLat - eps && minLon < maxLon - eps
}

export const boundsContain = (outer: LngLatBounds, inner: LngLatBounds, eps = 1e-7) => {
  const [[outerMinLon, outerMinLat], [outerMaxLon, outerMaxLat]] = outer
    .adjustAntiMeridian()
    .toArray()
  const [[innerMinLon, innerMinLat], [innerMaxLon, innerMaxLat]] = inner
    .adjustAntiMeridian()
    .toArray()

  return (
    innerMinLon >= outerMinLon - eps &&
    innerMinLat >= outerMinLat - eps &&
    innerMaxLon <= outerMaxLon + eps &&
    innerMaxLat <= outerMaxLat + eps
  )
}

export const boundsEqual = (
  bounds1: LngLatBounds | null | undefined,
  bounds2: LngLatBounds | null | undefined,
  eps = 1e-7,
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
    Math.abs(minLon1 - minLon2) < eps &&
    Math.abs(minLat1 - minLat2) < eps &&
    Math.abs(maxLon1 - maxLon2) < eps &&
    Math.abs(maxLat1 - maxLat2) < eps
  )
}

/** Pad bounds to grow/shrink them */
export const boundsPadding = (bounds: LngLatBounds, padding?: number) => {
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
  ] satisfies Bounds
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
  const {
    padBounds = 0.2,
    maxZoom = 18,
    intersects = false,
    minProportion = 0.00035,
    animate = false,
  } = opts ?? {}

  const mapBounds = map.getBounds().adjustAntiMeridian()
  const boundsAdjusted = bounds.adjustAntiMeridian()
  const boundsPadded = boundsPadding(boundsAdjusted, padBounds)

  const currentZoom = map.getZoom()
  const fitMaxZoom = Math.max(currentZoom, maxZoom)

  const maplibreOpts: MaplibreFitBoundsOptions = {
    maxZoom: fitMaxZoom,
    animate,
  }

  const isOffscreen = intersects
    ? !boundsIntersect(mapBounds, boundsPadded)
    : !boundsContain(mapBounds, boundsPadded)

  if (isOffscreen) {
    map.fitBounds(boundsPadded, maplibreOpts)
    return { reason: "offscreen", fitMaxZoom }
  }

  if (minProportion > 0 && fitMaxZoom > currentZoom) {
    const proportion = boundsSize(boundsAdjusted) / boundsSize(mapBounds)
    if (proportion > 0 && proportion < minProportion) {
      map.fitBounds(boundsPadded, maplibreOpts)
      return { reason: "small", fitMaxZoom }
    }
  }

  return null
}

export const boundsUnion = (left: Bounds | null | undefined, right: Bounds) =>
  left
    ? ([
        Math.min(left[0], right[0]),
        Math.min(left[1], right[1]),
        Math.max(left[2], right[2]),
        Math.max(left[3], right[3]),
      ] satisfies Bounds)
    : right
