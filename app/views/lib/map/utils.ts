import {
    LngLatBounds,
    type Map as MaplibreMap,
    Point,
    type PositionAnchor,
} from "maplibre-gl"
import { isLatitude, isLongitude } from "../../lib/utils"
import type { Bounds } from "../types"

const minBoundsSizePx = 20

export const markerIconAnchor: PositionAnchor = "bottom"

export const getMarkerIconElement = (
    color: string,
    showShadow: boolean,
): HTMLElement => {
    const container = document.createElement("div")
    container.classList.add("marker-icon")
    if (showShadow) {
        const shadow = document.createElement("img")
        shadow.classList.add("marker-shadow")
        shadow.src = "/static/img/marker/shadow.webp"
        shadow.width = 41
        shadow.height = 41
        shadow.draggable = false
        container.appendChild(shadow)
    }
    const icon = document.createElement("img")
    icon.classList.add("marker-icon-inner")
    icon.src = `/static/img/marker/${color}.webp`
    icon.width = 25
    icon.height = 41
    icon.draggable = false
    container.appendChild(icon)
    // TODO: leaflet leftover
    // iconAnchor: [12, 41]
    return container
}

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

    // Return empty bounds if no intersection
    if (minLat > maxLat || minLon > maxLon) {
        return new LngLatBounds([minLon1, minLat1, minLon1, minLat1])
    }

    return new LngLatBounds([minLon, minLat, maxLon, maxLat])
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

/** Get the closest point on a segment */
export const closestPointOnSegment = (test: Point, start: Point, end: Point): Point => {
    const dx = end.x - start.x
    const dy = end.y - start.y
    if (dx === 0 && dy === 0) return new Point(start.x, start.y)

    // Calculate projection position (t) on line using dot product
    // t = ((test-start) * (end-start)) / |end-start|²
    const t = Math.max(
        0,
        Math.min(
            1,
            ((test.x - start.x) * dx + (test.y - start.y) * dy) / (dx ** 2 + dy ** 2),
        ),
    )
    return new Point(start.x + t * dx, start.y + t * dy)
}

export const configureDefaultMapBehavior = (map: MaplibreMap): void => {
    map.setProjection({ type: "mercator" })

    map.dragRotate.disable()
    map.keyboard.disableRotation()
    map.touchZoomRotate.disableRotation()

    // Use constant zoom rate for consistent behavior
    // https://github.com/maplibre/maplibre-gl-js/issues/5367
    const zoomRate = 1 / 300
    map.scrollZoom.setWheelZoomRate(zoomRate)
    map.scrollZoom.setZoomRate(zoomRate)
}

/** Parse a simple "lat, lon" string into [lon, lat]. Returns null if invalid. */
export const tryParsePoint = (text: string): [number, number] | null => {
    if (!text) return null
    const parts = text.split(",")
    if (parts.length !== 2) return null
    const lat = Number.parseFloat(parts[0].trim())
    const lon = Number.parseFloat(parts[1].trim())
    return isLatitude(lat) && isLongitude(lon) ? [lon, lat] : null
}
