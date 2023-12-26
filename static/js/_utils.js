import * as L from "leaflet"
import { qsParse } from "./_qs.js"

// Check if number is a valid latitude
export const isLatitude = (lat) => lat >= -90 && lat <= 90

// Check if number is a valid longitude
export const isLongitude = (lon) => lon >= -180 && lon <= 180

// Check if number is a valid zoom level
export const isZoom = (zoom) => zoom >= 0 && zoom <= 25

// Compute the coordinate precision for a given zoom level
export const zoomPrecision = (zoom) => Math.max(0, Math.ceil(Math.log(zoom) / Math.LN2))

// Create a hash string for a state
// Accepts either a map object or an object with the following properties:
//   center: LatLng
//   zoom: number
//   layers: string
// Returns a string like "#map=15/51.505/-0.09&layers=BT"
export const formatHash = (args) => {
    let center
    let zoom
    let layers

    if (args instanceof L.Map) {
        center = args.getCenter()
        zoom = args.getZoom()
        layers = args.getLayersCode()
    } else {
        center = args.center || L.latLng(args.lat, args.lon)
        zoom = args.zoom
        layers = args.layers || ""
    }

    center = center.wrap()
    layers = layers.replace("M", "") // Standard layer is the default (implicit)

    const precision = zoomPrecision(zoom)
    const lat = center.lat.toFixed(precision)
    const lon = center.lng.toFixed(precision)

    const hash = layers ? `#map=${zoom}/${lat}/${lon}&layers=${layers}` : `#map=${zoom}/${lat}/${lon}`
    return hash
}

// Parse a hash string into a state
export const parseHash = (hash) => {
    const result = {}

    // Skip if there's no hash
    const i = hash.indexOf("#")
    if (i < 0) return result

    // Parse the hash as a query string
    const params = qsParse(hash.slice(i + 1))

    // Assign map state only if present and length is 3
    if (params.map) {
        const components = params.map.split("/")
        if (components.length === 3) {
            const zoom = parseInt(components[0], 10)
            const lat = parseFloat(components[1])
            const lon = parseFloat(components[2])

            // Assign position only if it's valid
            if (isZoom(result.zoom) && isLatitude(lat) && isLongitude(lon)) {
                result.zoom = zoom
                result.center = L.latLng(lat, lon)
            }
        }
    }

    // Assign layers only if present
    if (params.layers) result.layers = params.layers

    return result
}

// Throttle a function to only be called once every `delay` milliseconds
export const throttle = (func, delay) => {
    let lastCalled = 0
    let timeoutId = null

    return (...args) => {
        if (timeoutId) clearTimeout(timeoutId)
        const now = performance.now()
        const timeElapsed = now - lastCalled
        const timeLeft = delay - timeElapsed

        if (timeLeft <= 0) {
            lastCalled = now
            func(...args)
        } else {
            timeoutId = setTimeout(() => {
                lastCalled = performance.now()
                func(...args)
            }, timeLeft)
        }
    }
}
