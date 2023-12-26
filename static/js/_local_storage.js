import { isLatitude, isLongitude, isZoom, zoomPrecision } from "./_utils.js"

// Get last location from local storage
export const getLastLocation = () => {
    const lastLocation = localStorage.getItem("lastLocation")
    if (!lastLocation) return null
    const { lon, lat, zoom, layer } = JSON.parse(lastLocation)
    if (isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
        return {
            lon: lon,
            lat: lat,
            zoom: zoom,
            layer: layer,
        }
    }

    return null
}

// Set last location to local storage
export const setLastLocation = (lon, lat, zoom, layer = "") => {
    const precision = zoomPrecision(zoom)
    localStorage.setItem(
        "lastLocation",
        JSON.stringify({
            lon: lon.toFixed(precision),
            lat: lat.toFixed(precision),
            zoom: zoom,
            layer: layer,
        }),
    )
}
