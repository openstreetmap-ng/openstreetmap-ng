import * as L from "leaflet"

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
