import { isLatitude, isLongitude, isZoom, zoomPrecision } from "./_utils.js"

// Get last location from local storage
export const getLastLocation = () => {
    const lastLocation = localStorage.getItem("lastLocation")
    if (!lastLocation) return null
    const { lon, lat, zoom, layersCode } = JSON.parse(lastLocation)
    if (isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
        return {
            lon: lon,
            lat: lat,
            zoom: zoom,
            layersCode: layersCode,
        }
    }

    return null
}

// Set last location to local storage
export const setLastLocation = (lon, lat, zoom, layersCode = "") => {
    const precision = zoomPrecision(zoom)
    localStorage.setItem(
        "lastLocation",
        JSON.stringify({
            lon: lon.toFixed(precision),
            lat: lat.toFixed(precision),
            zoom: zoom,
            layersCode: layersCode,
        }),
    )
}
