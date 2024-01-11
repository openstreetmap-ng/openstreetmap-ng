import { isLatitude, isLongitude, isZoom, zoomPrecision } from "./_utils.js"

const mapStateVersion = 1

// Get last map state from local storage
export const getLastMapState = () => {
    const lastMapState = localStorage.getItem("lastMapState")
    if (!lastMapState) return null
    const { version, lon, lat, zoom, layersCode } = JSON.parse(lastMapState)

    // Check if values are valid
    if (version === mapStateVersion && isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
        return {
            lon: lon,
            lat: lat,
            zoom: zoom,
            layersCode: layersCode,
        }
    }

    return {
        lon: null,
        lat: null,
        zoom: null,
        layersCode: "",
    }
}

// Set last map state to local storage
export const setLastMapState = (lon, lat, zoom, layersCode = "") => {
    const precision = zoomPrecision(zoom)
    localStorage.setItem(
        "lastMapState",
        JSON.stringify({
            version: mapStateVersion,
            lon: lon.toFixed(precision),
            lat: lat.toFixed(precision),
            zoom: zoom,
            layersCode: layersCode,
        }),
    )
}
