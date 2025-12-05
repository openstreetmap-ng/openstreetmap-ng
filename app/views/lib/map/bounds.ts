import type { Bounds } from "@lib/types"
import { LngLatBounds, type Map as MaplibreMap } from "maplibre-gl"

const minBoundsSizePx = 20

/** Get the bounds area in square degrees */
export const getLngLatBoundsSize = (bounds: LngLatBounds): number => {
    const [[minLon, minLat], [maxLon, maxLat]] = bounds.adjustAntiMeridian().toArray()
    return (maxLon - minLon) * (maxLat - minLat)
}

/** Get the intersection of two bounds */
export const getLngLatBoundsIntersection = (
    bounds1: LngLatBounds,
    bounds2: LngLatBounds,
): LngLatBounds => {
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

/** Check if two bounds intersect */
export const checkLngLatBoundsIntersection = (
    bounds1: LngLatBounds,
    bounds2: LngLatBounds,
): boolean => {
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

/** Check if two bounds are equal */
export const lngLatBoundsEqual = (
    bounds1?: LngLatBounds,
    bounds2?: LngLatBounds,
): boolean => {
    if (!bounds1 && !bounds2) return true
    if (!bounds1 || !bounds2) return false
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
export const padLngLatBounds = (
    bounds: LngLatBounds,
    padding?: number,
): LngLatBounds => {
    if (!padding) return bounds
    const [[minLon, minLat], [maxLon, maxLat]] = bounds.adjustAntiMeridian().toArray()
    const paddingX = padding * (maxLon - minLon)
    const paddingY = padding * (maxLat - minLat)
    return new LngLatBounds([
        minLon - paddingX,
        Math.max(minLat - paddingY, -85),
        maxLon + paddingX,
        Math.min(maxLat + paddingY, 85),
    ])
}

/** Make bounds minimum size to make them easier to click */
export const makeBoundsMinimumSize = (map: MaplibreMap, bounds: Bounds): Bounds => {
    const [minLon, minLat, maxLon, maxLat] = bounds
    const mapBottomLeft = map.project([minLon, minLat])
    const mapTopRight = map.project([maxLon, maxLat])
    const width = mapTopRight.x - mapBottomLeft.x
    const height = mapBottomLeft.y - mapTopRight.y

    if (width < minBoundsSizePx) {
        const diff = minBoundsSizePx - width
        mapBottomLeft.x -= diff / 2
        mapTopRight.x += diff / 2
    }

    if (height < minBoundsSizePx) {
        const diff = minBoundsSizePx - height
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
    ]
}

/** Union two bounds, returning a new bounds */
export const unionBounds = (left: Bounds | null, right: Bounds): Bounds =>
    left
        ? [
              Math.min(left[0], right[0]),
              Math.min(left[1], right[1]),
              Math.max(left[2], right[2]),
              Math.max(left[3], right[3]),
          ]
        : right
