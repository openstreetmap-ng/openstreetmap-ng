import { LngLatBounds, type Map as MaplibreMap, type PositionAnchor } from "maplibre-gl"

import type { Bounds } from "../_types"

const minBoundsSizePx = 20

export const markerIconAnchor: PositionAnchor = "top"

export const getMarkerIconElement = (color: string, showShadow: boolean): HTMLElement => {
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
    const sw = bounds.getSouthWest()
    const ne = bounds.getNorthEast()
    return (ne.lng - sw.lng) * (ne.lat - sw.lat)
}

/** Get the intersection of two bounds */
export const getLngLatBoundsIntersection = (bounds1: LngLatBounds, bounds2: LngLatBounds): LngLatBounds => {
    const minLat1 = bounds1.getSouth()
    const maxLat1 = bounds1.getNorth()
    const minLon1 = bounds1.getWest()
    const maxLon1 = bounds1.getEast()

    const minLat2 = bounds2.getSouth()
    const maxLat2 = bounds2.getNorth()
    const minLon2 = bounds2.getWest()
    const maxLon2 = bounds2.getEast()

    const minLat = Math.max(minLat1, minLat2)
    const maxLat = Math.min(maxLat1, maxLat2)
    const minLon = Math.max(minLon1, minLon2)
    const maxLon = Math.min(maxLon1, maxLon2)

    // Return null bounds if no intersection
    if (minLat > maxLat || minLon > maxLon) {
        return new LngLatBounds([0, 0, 0, 0])
    }

    return new LngLatBounds([minLon, minLat, maxLon, maxLat])
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

    const latLngBottomLeft = map.unproject(mapBottomLeft)
    const latLngTopRight = map.unproject(mapTopRight)
    return [latLngBottomLeft.lng, latLngBottomLeft.lat, latLngTopRight.lng, latLngTopRight.lat]
}

export const disableMapRotation = (map: MaplibreMap): void => {
    map.dragRotate.disable()
    map.keyboard.disableRotation()
    map.touchZoomRotate.disableRotation()
}
