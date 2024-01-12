import * as L from "leaflet"

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

// Get the size (area in square degrees) of a LatLngBounds
export const getLatLngBoundsSize = (latLngBounds) => {
    const sw = latLngBounds.getSouthWest()
    const ne = latLngBounds.getNorthEast()
    return (ne.lng - sw.lng) * (ne.lat - sw.lat)
}
