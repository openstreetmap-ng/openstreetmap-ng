import * as L from "leaflet"
import { homePoint } from "./_dataset.js"
import { getLastMapState } from "./_local-storage.js"
import { qsParse, qsStringify } from "./_qs.js"
import { shortLinkEncode } from "./_shortlink.js"
import { getMapLayersCode } from "./leaflet/_utils.js"

// Check if number is a valid longitude
export const isLongitude = (lon) => lon >= -180 && lon <= 180

// Check if number is a valid latitude
export const isLatitude = (lat) => lat >= -90 && lat <= 90

// Check if number is a valid zoom level
export const isZoom = (zoom) => zoom >= 0 && zoom <= 25

// Compute the coordinate precision for a given zoom level
export const zoomPrecision = (zoom) => Math.max(0, Math.ceil(Math.log(zoom) / Math.LN2))

// TODO: always map?
// Create a hash string for a state
// Accepts either a map object or an object with the following properties:
//   center: LatLng
//   zoom: number
//   layers: string
// Returns a string like "#map=15/51.505/-0.09&layers=BT"
export const formatHash = (args) => {
    let center
    let zoom
    let layersCode

    if (args instanceof L.Map) {
        const map = args
        center = map.getCenter()
        zoom = map.getZoom()
        layersCode = getMapLayersCode(map)
    } else {
        center = args.center || L.latLng(args.lat, args.lon)
        center = center.wrap()
        zoom = args.zoom
        layersCode = args.layers || ""
    }

    const precision = zoomPrecision(zoom)
    const lat = center.lat.toFixed(precision)
    const lon = center.lng.toFixed(precision)

    const hash = layersCode ? `#map=${zoom}/${lat}/${lon}&layers=${layersCode}` : `#map=${zoom}/${lat}/${lon}`
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
    if (params.layers) result.layersCode = params.layers

    return result
}

// Get a URL for the current map location, optionally including a marker
export const getMapUrl = (map, showMarker = false) => {
    const center = map.getCenter()
    const zoom = map.getZoom()
    const precision = zoomPrecision(zoom)
    const lat = center.lat.toFixed(precision)
    const lon = center.lng.toFixed(precision)
    const hash = formatHash(map)

    if (showMarker) {
        return `${location.protocol}//${location.host}/?mlat=${lat}&mlon=${lon}${hash}`
    }

    return `${location.protocol}//${location.host}/${hash}`
}

// Get a short URL for the current map location, optionally including a marker
export const getMapShortUrl = (map, showMarker = false) => {
    const center = map.getCenter()
    const zoom = map.getZoom()
    const layersCode = getMapLayersCode(map)
    const precision = zoomPrecision(zoom)
    const lat = center.lat.toFixed(precision)
    const lon = center.lng.toFixed(precision)

    const code = shortLinkEncode(lon, lat, zoom)
    const params = {}

    if (layersCode) params.layers = layersCode
    if (showMarker) params.m = ""

    let protocol = "https:"
    let host = "osm.org"

    // Use the current protocol and host if running locally
    if (location.hostname === "localhost" || location.hostname === "127.0.0.1") {
        protocol = location.protocol
        host = location.host
    }

    if (Object.keys(params).length > 0) {
        return `${protocol}//${host}/go/${code}?${qsStringify(params)}`
    }

    return `${protocol}//${host}/go/${code}`
}

// Get HTML for embedding the current map location, optionally including a marker
export const getMapEmbedHtml = (map, markerLatLng = null) => {
    const bbox = map.getBounds().toBBoxString()
    const layerId = map.getBaseLayerId()

    const params = {
        bbox: bbox,
        layer: layerId,
    }

    if (markerLatLng) {
        // Don't apply precision on embeds
        const lat = markerLatLng.lat
        const lon = markerLatLng.lng
        params.marker = `${lat},${lon}`
    }

    // Container for HTML generation
    const container = document.createElement("div")

    // Create the iframe
    const iframe = document.createElement("iframe")
    iframe.width = 425
    iframe.height = 350
    iframe.src = `${location.protocol}//${location.host}/export/embed.html?${qsStringify(params)}`
    iframe.style.border = "1px solid black"
    container.appendChild(iframe)

    // Create the link to view the larger map
    const small = document.createElement("small")
    const link = document.createElement("a")
    link.href = getMapUrl(map, markerLatLng)
    link.textContent = I18n.t("javascripts.share.view_larger_map")
    small.appendChild(link)
    container.appendChild(small)

    return container.innerHTML
}

// Get a geo URI for the current map location
export const getGeoUri = (map) => {
    const center = map.getCenter()
    const zoom = map.getZoom()
    const precision = zoomPrecision(zoom)
    const lat = center.lat.toFixed(precision)
    const lon = center.lng.toFixed(precision)
    return `geo:${lat},${lon}?z=${zoom}`
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
    const lastLocation = getLastMapState()

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
    result.layer = state.layersCode || lastLocation?.layersCode || ""

    // Apply optional scaling
    const scale = parseFloat(searchParams.scale)
    if (scale > 0) result.zoom = Math.log(360 / (scale * 512)) / Math.log(2)

    return result
}
