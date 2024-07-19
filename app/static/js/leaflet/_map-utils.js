import i18next from "i18next"
import * as L from "leaflet"
import { homePoint } from "../_config.js"
import { getLastMapState, setLastMapState } from "../_local-storage.js"
import { qsEncode, qsParse } from "../_qs.js"
import { shortLinkEncode } from "../_shortlink.js"
import { timezoneBoundsMap } from "../_timezone-bbox.js"
import "../_types.js"
import { isLatitude, isLongitude, isZoom, mod, zoomPrecision } from "../_utils.js"
import { getBaseLayerById, getLayerIdByCode, getOverlayLayerById } from "./_layers.js"

/**
 * Encode current layers to a string using layer codes
 * @param {L.Map} map Leaflet map
 * @returns {string} Layers code
 * @example
 * getMapLayersCode(map)
 * // => "BT"
 */
export const getMapLayersCode = (map) => {
    const layerCodes = []
    map.eachLayer((layer) => {
        if (layer.options.layerCode) layerCodes.push(layer.options.layerCode)
    })
    return layerCodes.join("")
}

/**
 * Get the base layer id of the map
 * @param {L.Map} map Leaflet map
 * @returns {string} Base layer id
 * @example
 * getMapBaseLayerId(map)
 * // => "standard"
 */
export const getMapBaseLayerId = (map) => {
    let baseLayerId = null
    map.eachLayer((layer) => {
        if (getBaseLayerById(layer.options.layerId)) baseLayerId = layer.options.layerId
    })
    if (!baseLayerId) throw new Error("No base layer found")
    return baseLayerId
}

/**
 * Get the base layer instance of the map
 * @param {L.Map} map Leaflet map
 * @returns {L.Layer} Base layer instance
 */
export const getMapBaseLayer = (map) => {
    let baseLayer = null
    map.eachLayer((layer) => {
        if (getBaseLayerById(layer.options.layerId)) baseLayer = layer
    })
    if (!baseLayer) throw new Error("No base layer found")
    return baseLayer
}

/**
 * Set the map layers from a layers code
 * @param {L.Map} map Leaflet map
 * @param {string} layersCode Layers code
 * @returns {void}
 * @example
 * setMapLayersCode(map, "BT")
 */
const setMapLayersCode = (map, layersCode) => {
    console.debug("setMapLayersCode", layersCode)
    const layersIds = new Set()

    // Extract base layers for validation and to check
    // whether we need to auto-add the default base layer
    const baseLayers = []

    for (const layerCode of layersCode) {
        const layerId = getLayerIdByCode(layerCode)
        layersIds.add(layerId)

        const baseLayer = getBaseLayerById(layerId)
        if (baseLayer) baseLayers.push(baseLayer)
    }

    if (baseLayers.length > 1) {
        console.error("Invalid layers code (too many base layers)", layersCode)
        return
    }

    // Add default base layer if no base layer is present
    if (!baseLayers.length) {
        const layerId = getLayerIdByCode("")
        layersIds.add(layerId)
        const layer = getBaseLayerById(layerId)
        baseLayers.push(layer)
    }

    // Remove layers not found in the code
    map.eachLayer((layer) => {
        const layerId = layer.options.layerId
        if (!layerId || layerId === "focus") return
        if (layersIds.has(layerId)) {
            console.debug("Keeping layer", layerId)
            layersIds.delete(layerId)
            return
        }

        if (getOverlayLayerById(layerId)) {
            console.debug("Removing overlay layer", layerId)
            map.removeLayer(layer)
            map.fire("overlayremove", { layer, name: layerId })
        } else {
            console.debug("Removing base layer", layerId)
            map.removeLayer(layer)
        }
    })

    // Add missing layers
    for (const layerId of layersIds) {
        const baseLayer = getBaseLayerById(layerId)
        if (baseLayer) {
            console.debug("Adding base layer", layerId)
            map.addLayer(baseLayer)

            // Trigger the baselayerchange event
            // https://leafletjs.com/reference.html#map-baselayerchange
            // https://leafletjs.com/reference.html#layerscontrolevent
            map.fire("baselayerchange", { layer: baseLayer, name: layerId })
        } else {
            const overlayLayer = getOverlayLayerById(layerId)
            console.debug("Adding overlay layer", layerId)
            map.addLayer(overlayLayer)
            map.fire("overlayadd", { layer: overlayLayer, name: layerId })
        }
    }
}

/**
 * Get the current map state object
 * @param {L.Map} map Leaflet map
 * @returns {MapState} Map state object
 */
export const getMapState = (map) => {
    const center = map.getCenter()
    const lon = mod(center.lng + 180, 360) - 180
    const lat = center.lat
    const zoom = map.getZoom()
    const layersCode = getMapLayersCode(map)
    return { lon, lat, zoom, layersCode }
}

/**
 * Set the map state from a state object
 * @param {L.Map} map Leaflet map
 * @param {MapState} state Map state object
 * @param {object} options Options for setView
 * @returns {void}
 */
export const setMapState = (map, state, options) => {
    console.debug("setMapState", state)
    const { lon, lat, zoom, layersCode } = state
    map.setView(L.latLng(lat, lon), zoom, options)
    setMapLayersCode(map, layersCode)
    setLastMapState(state)
}

/**
 * Create a hash string for a map state
 * @param {MapState} state Map state object
 * @returns {string} Hash string
 * @example
 * encodeMapState(state)
 * // => "#map=15/51.505/-0.09&layers=BT"
 */
export const encodeMapState = (state) => {
    let { lon, lat, zoom, layersCode } = state
    const precision = zoomPrecision(zoom)
    lon = mod(lon + 180, 360) - 180
    lon = lon.toFixed(precision)
    lat = lat.toFixed(precision)
    const hash = layersCode ? `#map=${zoom}/${lat}/${lon}&layers=${layersCode}` : `#map=${zoom}/${lat}/${lon}`
    return hash
}

/**
 * Parse a hash string into a map state object
 * @param {string} hash Hash string
 * @returns {MapState|null} Map state object or null if invalid
 * @example
 * parseMapState("#map=15/51.505/-0.09&layers=BT")
 * // => { lon: -0.09, lat: 51.505, zoom: 15, layersCode: "BT" }
 */
export const parseMapState = (hash) => {
    // Skip if there's no hash
    const i = hash.indexOf("#")
    if (i < 0) return null

    // Parse the hash as a query string
    const params = qsParse(hash.slice(i + 1))

    // Hash string must contain map parameter
    if (!params.map) return null

    // Map must contain zoom, lat, lon parameters
    const components = params.map.split("/")
    if (components.length !== 3) return null

    const zoom = Number.parseInt(components[0], 10)
    const lat = Number.parseFloat(components[1])
    const lon = Number.parseFloat(components[2])

    // Each component must be in a valid format
    if (!(isZoom(zoom) && isLatitude(lat) && isLongitude(lon))) return null

    return {
        lon: lon,
        lat: lat,
        zoom: zoom,
        layersCode: params.layers ?? "",
    }
}

/**
 * Convert bounds to a lon, lat, zoom object
 * @param {L.Map|null} map Optional leaflet map for improved bounds detection
 * @param {number[]} bounds Bounds array in the [minLon, minLat, maxLon, maxLat] format
 * @returns {object} { lon, lat, zoom } object
 */
const convertBoundsToLonLatZoom = (map, bounds) => {
    const [minLon, minLat, maxLon, maxLat] = bounds
    const lon = (minLon + maxLon) / 2
    const lat = (minLat + maxLat) / 2

    if (map) {
        const zoom = map.getBoundsZoom(L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon)))
        return { lon, lat, zoom }
    }

    const latRad = (lat) => Math.sin((lat * Math.PI) / 180)
    const getZoom = (mapPx, worldPx, fraction) => Math.floor(Math.log(mapPx / worldPx / fraction) / Math.LN2)

    // Calculate the fraction of the world that the longitude and latitude take up
    const latFraction = (latRad(maxLat) - latRad(minLat)) / Math.PI
    const lonDiff = maxLon - minLon
    const lonFraction = (lonDiff < 0 ? lonDiff + 360 : lonDiff) / 360

    // Assume the map takes up the entire screen
    const mapHeight = window.innerHeight
    const mapWidth = window.innerWidth

    // Calculate the maximum zoom level at which the entire bounds would fit in the map view
    const tileSize = 256
    const maxLatZoom = getZoom(mapHeight, tileSize, latFraction)
    const maxLonZoom = getZoom(mapWidth, tileSize, lonFraction)

    const zoom = Math.min(maxLatZoom, maxLonZoom)
    return { lon, lat, zoom }
}

/**
 * Get initial (default) map state by analyzing various parameters
 * @param {L.Map|null} map Optional leaflet map for improved bounds detection
 * @returns {MapState} Map state object
 * @example
 * getInitialMapState()
 * // => { lon: -0.09, lat: 51.505, zoom: 15, layersCode: "BT" }
 */
export const getInitialMapState = (map = null) => {
    // TODO: check if hash is set
    const hashState = parseMapState(location.hash)

    // 1. Use the position from the hash state
    if (hashState) return hashState

    // Delay search parsing, most URLs have a valid hash state
    const searchParams = qsParse(location.search.substring(1))
    const lastState = getLastMapState()

    // 2. Use the bounds from the bbox query parameter
    if (searchParams.bbox) {
        const bbox = searchParams.bbox.split(",").map(Number.parseFloat)
        if (bbox.length === 4) {
            const { lon, lat, zoom } = convertBoundsToLonLatZoom(map, bbox)
            return { lon, lat, zoom, layersCode: lastState?.layersCode ?? "" }
        }
    }

    // 3. Use the bounds from minlon, minlat, maxlon, maxlat query parameters
    if (searchParams.minlon && searchParams.minlat && searchParams.maxlon && searchParams.maxlat) {
        const minLon = Number.parseFloat(searchParams.minlon)
        const minLat = Number.parseFloat(searchParams.minlat)
        const maxLon = Number.parseFloat(searchParams.maxlon)
        const maxLat = Number.parseFloat(searchParams.maxlat)
        if (isLongitude(minLon) && isLatitude(minLat) && isLongitude(maxLon) && isLatitude(maxLat)) {
            const { lon, lat, zoom } = convertBoundsToLonLatZoom(map, [minLon, minLat, maxLon, maxLat])
            return { lon, lat, zoom, layersCode: lastState?.layersCode ?? "" }
        }
    }

    // 4. Use the position from the marker
    if (searchParams.mlon && searchParams.mlat) {
        const mlon = Number.parseFloat(searchParams.mlon)
        const mlat = Number.parseFloat(searchParams.mlat)
        const zoom = Number.parseInt(searchParams.zoom ?? 12, 10)
        if (isLongitude(mlon) && isLatitude(mlat) && isZoom(zoom)) {
            return { lon: mlon, lat: mlat, zoom, layersCode: lastState?.layersCode ?? "" }
        }
    }

    // 5. Use the position from lat/lon search parameters
    if (searchParams.lon && searchParams.lat) {
        const lon = Number.parseFloat(searchParams.lon)
        const lat = Number.parseFloat(searchParams.lat)
        const zoom = Number.parseInt(searchParams.zoom ?? 12, 10)
        if (isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
            return { lon, lat, zoom, layersCode: lastState?.layersCode ?? "" }
        }
    }

    // 6. Use the last location from local storage
    if (lastState) return lastState

    // 7. Use the user home location
    if (homePoint) {
        const [lon, lat] = homePoint
        const zoom = 15 // Home zoom defaults to 15
        return { lon, lat, zoom, layersCode: "" }
    }

    // 8. Use the user's country bounds
    const timezoneName = Intl.DateTimeFormat().resolvedOptions().timeZone
    const countryBounds = timezoneBoundsMap.get(timezoneName)
    if (countryBounds) {
        const { lon, lat, zoom } = convertBoundsToLonLatZoom(map, countryBounds)
        return { lon, lat, zoom, layersCode: "" }
    }

    // 9. Use the default location
    return {
        lon: 0,
        lat: 30,
        zoom: 3,
        layersCode: "",
    }
}

/**
 * Get a URL for the current map location
 * @param {L.Map} map Leaflet map
 * @param {boolean} showMarker Whether to include a marker
 * @returns {string} Map URL
 * @example
 * getMapUrl(map)
 * // => "https://www.openstreetmap.org/#map=15/51.505/-0.09&layers=BT"
 */
export const getMapUrl = (map, showMarker = false) => {
    let { lon, lat, zoom, layersCode } = getMapState(map)
    const precision = zoomPrecision(zoom)
    const hash = encodeMapState({ lon, lat, zoom, layersCode })
    lon = lon.toFixed(precision)
    lat = lat.toFixed(precision)

    if (showMarker) {
        return `${location.protocol}//${location.host}/?mlat=${lat}&mlon=${lon}${hash}`
    }

    return `${location.protocol}//${location.host}/${hash}`
}

/**
 * Get a short URL for the current map location
 * @param {L.Map} map Leaflet map
 * @param {boolean} showMarker Whether to include a marker
 * @returns {string} Short map URL
 * @example
 * getMapShortUrl(map)
 * // => "https://osm.org/go/wF7ZdNbjU-"
 */
export const getMapShortUrl = (map, showMarker = false) => {
    const { lon, lat, zoom, layersCode } = getMapState(map)
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

    if (Object.keys(params).length) {
        return `${protocol}//${host}/go/${code}?${qsEncode(params)}`
    }

    return `${protocol}//${host}/go/${code}`
}

/**
 * Get HTML for embedding the current map location
 * @param {L.Map} map Leaflet map
 * @param {L.LatLng|null} markerLatLng Optional marker position
 * @returns {string} Embed HTML
 * @example
 * getMapEmbedHtml(map, L.latLng(51.505, -0.09))
 */
export const getMapEmbedHtml = (map, markerLatLng = null) => {
    const params = {
        bbox: map.getBounds().toBBoxString(),
        layer: getMapBaseLayer(map).options.layerId,
    }

    // Add optional map marker
    if (markerLatLng) {
        // Intentionally not applying precision on embed markers
        const lon = markerLatLng.lng
        const lat = markerLatLng.lat
        params.marker = `${lat},${lon}`
    }

    // Container for HTML generation
    const container = document.createElement("div")

    // Create the iframe
    const iframe = document.createElement("iframe")
    iframe.width = 425
    iframe.height = 350
    iframe.src = `${location.protocol}//${location.host}/export/embed.html?${qsEncode(params)}`
    iframe.style.border = "1px solid black"

    // allow-popups: allow links to open in a new window: "Report a problem", copyright
    // allow-popups-to-escape-sandbox: opened links should not be restricted by this sandbox
    // allow-scripts: allow the iframe to run javascript
    iframe.sandbox = "allow-popups allow-popups-to-escape-sandbox allow-scripts"

    container.appendChild(iframe)

    // Create new line
    const br = document.createElement("br")
    container.appendChild(br)

    // Create the link to view the larger map
    const small = document.createElement("small")
    const link = document.createElement("a")
    link.href = getMapUrl(map, Boolean(markerLatLng))
    link.textContent = i18next.t("javascripts.share.view_larger_map")
    small.appendChild(link)
    container.appendChild(small)

    return container.innerHTML
}

/**
 * Get a geo URI for the current map location
 * @param {L.Map} map Leaflet map
 * @returns {string} Geo URI
 * @example
 * getMapGeoUri(map)
 * // => "geo:51.505,-0.09?z=15"
 */
export const getMapGeoUri = (map) => {
    let { lon, lat, zoom } = getMapState(map)
    const precision = zoomPrecision(zoom)
    lon = lon.toFixed(precision)
    lat = lat.toFixed(precision)
    return `geo:${lat},${lon}?z=${zoom}`
}

/**
 * Clone a tile layer
 * @param {L.TileLayer} layer Layer to clone
 * @returns {L.TileLayer} Cloned layer
 */
export const cloneTileLayer = (layer) => {
    return new L.TileLayer(layer._url, layer.options)
}

/**
 * Add a control group to the map
 * @param {L.Map} map Leaflet map
 * @param {L.Control[]} controls Control instances
 * @returns {void}
 */
export const addControlGroup = (map, controls) => {
    for (const control of controls) {
        map.addControl(control)

        const container = control.getContainer()
        const classList = container.classList
        classList.add("leaflet-control-group")

        if (control === controls[0]) classList.add("first")
        if (control === controls[controls.length - 1]) classList.add("last")
    }
}

/**
 * Disable click propagation for map controls, to avoid map events being triggered by the controls
 * @param {L.Map} map Leaflet map
 * @returns {void}
 */
export const disableControlsClickPropagation = (map) => {
    const mapContainer = map.getContainer()
    const controlContainer = mapContainer.querySelector(".leaflet-control-container")
    if (controlContainer) {
        console.debug("Disabled click propagation for map controls")
        L.DomEvent.disableClickPropagation(controlContainer)
    } else {
        console.warn("Leaflet control container not found")
    }

    const mapAlertsContainer = mapContainer.querySelectorAll(".map-alert")
    for (const mapAlert of mapAlertsContainer) {
        L.DomEvent.disableClickPropagation(mapAlert)
    }
    console.debug("Disabled click propagation for", mapAlertsContainer.length, "map alerts")
}

/**
 * Get the map alert element
 * @param {string} name Alert name
 * @returns {HTMLElement} Alert element
 */
export const getMapAlert = (name) => {
    const alert = document.querySelector(`.map-alert.${name}`)
    if (!alert) console.error("Map alert", name, "not found")
    return alert
}
