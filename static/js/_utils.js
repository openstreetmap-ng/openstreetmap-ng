import * as L from "leaflet"
import { homePoint } from "./_dataset.js"
import { getLastLocation } from "./_local-storage.js"
import { qsParse } from "./_qs.js"

// Check if number is a valid longitude
export const isLongitude = (lon) => lon >= -180 && lon <= 180

// Check if number is a valid latitude
export const isLatitude = (lat) => lat >= -90 && lat <= 90

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
            if (isZoom(zoom) && isLatitude(lat) && isLongitude(lon)) {
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

// Convert parameters to map parameters
export const getMapParams = (searchParams) => {
    const result = {}
    // Slightly better type hinting
    result.lon = undefined
    result.lat = undefined
    result.zoom = undefined
    result.bounds = undefined

    // Marker parameters
    if (searchParams.mlat && searchParams.mlon) {
        const mlon = parseFloat(searchParams.mlon)
        const mlat = parseFloat(searchParams.mlat)
        if (isLongitude(mlon) && isLatitude(mlat)) {
            result.marker = true
            result.mlon = mlon
            result.mlat = mlat
        }
    }

    // Old style object parameters
    for (const type of ["node", "way", "relation", "note"]) {
        if (searchParams[type]) {
            const id = parseInt(searchParams[type], 10)
            if (id > 0) {
                result.object = { type: type, id: id }
                break
            }
        }
    }

    const state = parseHash(location.hash)
    const lastLocation = getLastLocation()

    // Decide on the initial position and zoom
    const setPosition = (result) => {
        // 1. Use the position from the hash state
        // (already validated)
        if (state.center) {
            result.lon = state.center.lng
            result.lat = state.center.lat
            result.zoom = state.zoom
            return
        }

        // 2. Use the bounds from the bbox query parameter
        if (searchParams.bbox) {
            const bbox = searchParams.bbox.split(",").map(parseFloat)
            if (bbox.length === 4) {
                const [minLon, minLat, maxLon, maxLat] = bbox
                if (isLongitude(minLon) && isLatitude(minLat) && isLongitude(maxLon) && isLatitude(maxLat)) {
                    result.bounds = L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
                    return
                }
            }
        }

        // 3. Use the bounds from minlon, minlat, maxlon, maxlat query parameters
        if (searchParams.minlon && searchParams.minlat && searchParams.maxlon && searchParams.maxlat) {
            const minLon = parseFloat(searchParams.minlon)
            const minLat = parseFloat(searchParams.minlat)
            const maxLon = parseFloat(searchParams.maxlon)
            const maxLat = parseFloat(searchParams.maxlat)
            if (isLongitude(minLon) && isLatitude(minLat) && isLongitude(maxLon) && isLatitude(maxLat)) {
                result.bounds = L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
                return
            }
        }

        // 4. Use the position from the marker
        if (result.marker) {
            const zoom = parseInt(searchParams.zoom || 12, 10)
            if (isZoom(zoom)) {
                result.lon = result.mlon
                result.lat = result.mlat
                result.zoom = zoom
                return
            }
        }

        // 5. Use the last location from local storage
        if (lastLocation) {
            result.lon = lastLocation.lon
            result.lat = lastLocation.lat
            result.zoom = lastLocation.zoom
            return
        }

        // 6. Use the user home location
        if (homePoint) {
            const [lon, lat] = JSON.parse(homePoint)
            result.lon = lon
            result.lat = lat
            result.zoom = 10
            return
        }

        // 7. Use the default location
        result.lon = 0
        result.lat = 30
        result.zoom = 3
    }

    setPosition(result)

    // Decide on the initial layer
    result.layer = state.layers || lastLocation?.layer || ""

    // Apply optional scaling
    const scale = parseFloat(searchParams.scale)
    if (scale > 0) result.zoom = Math.log(360 / (scale * 512)) / Math.log(2)

    return result
}
