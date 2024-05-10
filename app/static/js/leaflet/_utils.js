import * as L from "leaflet"

const minBoundsSizePx = 20

/**
 * Get a marker icon
 * @param {string} color Marker color/theme
 * @param {boolean} showShadow Whether to show the marker shadow
 * @returns {L.Icon} The marker icon
 */
export const getMarkerIcon = (color, showShadow) => {
    let shadowUrl = null
    let shadowSize = null

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

/**
 * Get the bounds area in square degrees
 * @param {L.LatLngBounds} bounds Leaflet bounds
 * @returns {number} The bounds area in square degrees
 */
export const getLatLngBoundsSize = (bounds) => {
    const sw = bounds.getSouthWest()
    const ne = bounds.getNorthEast()
    return (ne.lng - sw.lng) * (ne.lat - sw.lat)
}

/**
 * Make bounds minimum size to make them easier to click
 * @param {L.Map} map Leaflet map
 * @param {number[]} bounds The bounds in [minLon, minLat, maxLon, maxLat]
 * @returns {number[]} The new bounds
 */
export const makeBoundsMinimumSize = (map, bounds) => {
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
