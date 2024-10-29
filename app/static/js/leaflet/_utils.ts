import * as L from "leaflet"
import type { Bounds } from "../_types"

const minBoundsSizePx = 20

/** Get a marker icon */
export const getMarkerIcon = (color: string, showShadow: boolean): L.Icon => {
    let shadowUrl: string | null = null
    let shadowSize: [number, number] | null = null
    if (showShadow) {
        shadowUrl = "/static/img/marker/shadow.webp"
        shadowSize = [41, 41]
    }
    return L.icon({
        iconUrl: `/static/img/marker/${color}.webp`,
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowUrl: shadowUrl,
        shadowSize: shadowSize,
    })
}

/** Get the bounds area in square degrees */
export const getLatLngBoundsSize = (bounds: L.LatLngBounds): number => {
    const sw = bounds.getSouthWest()
    const ne = bounds.getNorthEast()
    return (ne.lng - sw.lng) * (ne.lat - sw.lat)
}

/** Get the intersection of two bounds */
export const getLatLngBoundsIntersection = (bounds1: L.LatLngBounds, bounds2: L.LatLngBounds): L.LatLngBounds => {
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
        return L.latLngBounds(L.latLng(0, 0), L.latLng(0, 0))
    }

    return L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
}

/** Make bounds minimum size to make them easier to click */
export const makeBoundsMinimumSize = (map: L.Map, bounds: Bounds): Bounds => {
    const [minLon, minLat, maxLon, maxLat] = bounds
    const mapBottomLeft = map.project(L.latLng(minLat, minLon))
    const mapTopRight = map.project(L.latLng(maxLat, maxLon))
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
