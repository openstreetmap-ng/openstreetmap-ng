import i18next from "i18next"
import * as L from "leaflet"
import { homePoint } from "../_config"
import { getLastMapState, setLastMapState } from "../_local-storage"
import { qsEncode, qsParse } from "../_qs"
import { shortLinkEncode } from "../_shortlink"
import { timezoneBoundsMap } from "../_timezone-bbox"
import type { Bounds } from "../_types"
import { isLatitude, isLongitude, isZoom, mod, zoomPrecision } from "../_utils"
import {
    type LayerCode,
    type LayerId,
    getBaseLayerById,
    getLayerData,
    getLayerIdByCode,
    getOverlayLayerById,
} from "./_layers"

export interface LonLat {
    lon: number
    lat: number
}

export interface LonLatZoom extends LonLat {
    zoom: number
}

export interface MapState extends LonLatZoom {
    layersCode?: string
}

/**
 * Encode current layers to a string using layer codes
 * @example
 * getMapLayersCode(map)
 * // => "BT"
 */
export const getMapLayersCode = (map: L.Map): string => {
    const layerCodes: LayerCode[] = []
    map.eachLayer((layer) => {
        const data = getLayerData(layer)
        if (data?.layerCode) layerCodes.push(data.layerCode)
    })
    return layerCodes.join("")
}

/**
 * Get the base layer id of the map
 * @example
 * getMapBaseLayerId(map)
 * // => "standard"
 */
export const getMapBaseLayerId = (map: L.Map): LayerId => {
    let baseLayerId: LayerId | null = null
    map.eachLayer((layer) => {
        const data = getLayerData(layer)
        if (data && getBaseLayerById(data.layerId)) baseLayerId = data.layerId
    })
    if (!baseLayerId) throw new Error("No base layer found")
    return baseLayerId
}

/** Get the base layer instance of the map */
export const getMapBaseLayer = (map: L.Map): L.TileLayer => {
    let baseLayer: L.TileLayer | null = null
    map.eachLayer((layer) => {
        const data = getLayerData(layer)
        if (data && getBaseLayerById(data.layerId)) baseLayer = layer as L.TileLayer
    })
    if (!baseLayer) throw new Error("No base layer found")
    return baseLayer
}

/**
 * Set the map layers from a layers code
 * @example
 * setMapLayersCode(map, "BT")
 */
const setMapLayersCode = (map: L.Map, layersCode?: string): void => {
    console.debug("setMapLayersCode", layersCode)
    const layersIds: Set<LayerId> = new Set()

    // Extract base layers for validation and to check
    // whether we need to auto-add the default base layer
    const baseLayers: L.TileLayer[] = []

    for (const layerCode of layersCode ?? "") {
        const layerId = getLayerIdByCode(layerCode as LayerCode)
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
        const layerId = getLayerIdByCode("" as LayerCode)
        layersIds.add(layerId)
        const layer = getBaseLayerById(layerId)
        baseLayers.push(layer)
    }

    // Remove layers not found in the code
    map.eachLayer((layer) => {
        const data = getLayerData(layer)
        if (!data) return
        const layerId = data.layerId
        if (layerId === "focus") return
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

/** Get the current map state object */
export const getMapState = (map: L.Map): MapState => {
    const center = map.getCenter()
    const lon = mod(center.lng + 180, 360) - 180
    const lat = center.lat
    const zoom = map.getZoom()
    const layersCode = getMapLayersCode(map)
    return { lon, lat, zoom, layersCode }
}

/** Set the map state from a state object */
export const setMapState = (map: L.Map, state: MapState, options?: L.ZoomPanOptions): void => {
    console.debug("setMapState", state)
    const { lon, lat, zoom, layersCode } = state
    map.setView(L.latLng(lat, lon), zoom, options)
    setMapLayersCode(map, layersCode)
    setLastMapState(state)
}

/**
 * Create a hash string for a map state
 * @example
 * encodeMapState(state)
 * // => "#map=15/51.505/-0.09&layers=BT"
 */
export const encodeMapState = (state: MapState): string => {
    let { lon, lat, zoom, layersCode } = state
    const precision = zoomPrecision(zoom)
    lon = mod(lon + 180, 360) - 180
    const lonFixed = lon.toFixed(precision)
    const latFixed = lat.toFixed(precision)
    return layersCode
        ? `#map=${zoom}/${latFixed}/${lonFixed}&layers=${layersCode}`
        : `#map=${zoom}/${latFixed}/${lonFixed}`
}

/**
 * Parse a hash string into a map state object
 * @example
 * parseMapState("#map=15/51.505/-0.09&layers=BT")
 * // => { lon: -0.09, lat: 51.505, zoom: 15, layersCode: "BT" }
 */
export const parseMapState = (hash: string): MapState | null => {
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
        layersCode: params.layers,
    }
}

/** Convert bounds to a lon, lat, zoom object */
const convertBoundsToLonLatZoom = (map: L.Map | null, bounds: Bounds): LonLatZoom => {
    const [minLon, minLat, maxLon, maxLat] = bounds
    const lon = (minLon + maxLon) / 2
    const lat = (minLat + maxLat) / 2

    if (map) {
        const zoom = map.getBoundsZoom(L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon)))
        return { lon, lat, zoom }
    }

    const latRad = (lat: number): number => Math.sin((lat * Math.PI) / 180)
    const getZoom = (mapPx: number, worldPx: number, fraction: number): number =>
        Math.floor(Math.log(mapPx / worldPx / fraction) / Math.LN2)

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
 * @example
 * getInitialMapState()
 * // => { lon: -0.09, lat: 51.505, zoom: 15, layersCode: "BT" }
 */
export const getInitialMapState = (map?: L.Map): MapState => {
    const hashState = parseMapState(window.location.hash)

    // 1. Use the position from the hash state
    if (hashState) return hashState

    // Delay search parsing, most URLs have a valid hash state
    const searchParams = qsParse(window.location.search.substring(1))
    const lastState = getLastMapState()

    // 2. Use the bounds from the bbox query parameter
    if (searchParams.bbox) {
        const bbox = searchParams.bbox.split(",").map(Number.parseFloat)
        if (bbox.length === 4) {
            const { lon, lat, zoom } = convertBoundsToLonLatZoom(map, bbox as Bounds)
            return { lon, lat, zoom, layersCode: lastState?.layersCode }
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
            return { lon, lat, zoom, layersCode: lastState?.layersCode }
        }
    }

    // 4. Use the position from the marker
    if (searchParams.mlon && searchParams.mlat) {
        const mlon = Number.parseFloat(searchParams.mlon)
        const mlat = Number.parseFloat(searchParams.mlat)
        const zoom = searchParams.zoom ? Number.parseInt(searchParams.zoom, 10) : 12
        if (isLongitude(mlon) && isLatitude(mlat) && isZoom(zoom)) {
            return { lon: mlon, lat: mlat, zoom, layersCode: lastState?.layersCode }
        }
    }

    // 5. Use the position from lat/lon search parameters
    if (searchParams.lon && searchParams.lat) {
        const lon = Number.parseFloat(searchParams.lon)
        const lat = Number.parseFloat(searchParams.lat)
        const zoom = searchParams.zoom ? Number.parseInt(searchParams.zoom, 10) : 12
        if (isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
            return { lon, lat, zoom, layersCode: lastState?.layersCode }
        }
    }

    // 6. Use the last location from local storage
    if (lastState) return lastState

    // 7. Use the user home location
    if (homePoint) {
        const { lon, lat } = homePoint
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
 * @example
 * getMapUrl(map)
 * // => "https://www.openstreetmap.org/#map=15/51.505/-0.09&layers=BT"
 */
export const getMapUrl = (map: L.Map, showMarker = false): string => {
    const state = getMapState(map)
    const hash = encodeMapState(state)
    const { lon, lat, zoom } = state
    if (showMarker) {
        const precision = zoomPrecision(zoom)
        const lonFixed = lon.toFixed(precision)
        const latFixed = lat.toFixed(precision)
        return `${window.location.origin}/?mlat=${latFixed}&mlon=${lonFixed}${hash}`
    }
    return `${window.location.origin}/${hash}`
}

const shortDomainUpgrades = new Map<string, string>([
    ["openstreetmap.org", "osm.org"],
    ["openstreetmap.ng", "osm.ng"],
])

/**
 * Get a short URL for the current map location
 * @example
 * getMapShortUrl(map)
 * // => "https://osm.org/go/wF7ZdNbjU-"
 */
export const getMapShortlink = (map: L.Map, showMarker = false): string => {
    const state = getMapState(map)
    const code = shortLinkEncode(state)
    const params: { [key: string]: string } = {}

    if (state.layersCode) params.layers = state.layersCode
    if (showMarker) params.m = ""

    // Upgrade to short domain when supported
    const hostname = location.hostname
    const tldPos = hostname.lastIndexOf(".")
    const domainPos = hostname.lastIndexOf(".", tldPos - 1)
    const shortDomainKey = domainPos > 0 ? hostname.substring(domainPos + 1) : hostname
    const host = shortDomainUpgrades.get(shortDomainKey) ?? location.host

    return Object.keys(params).length
        ? `${location.protocol}//${host}/go/${code}?${qsEncode(params)}`
        : `${location.protocol}//${host}/go/${code}`
}

/**
 * Get HTML for embedding the current map location
 * @example
 * getMapEmbedHtml(map, L.latLng(51.505, -0.09))
 */
export const getMapEmbedHtml = (map: L.Map, markerLatLng?: L.LatLng): string => {
    const layerData = getLayerData(getMapBaseLayer(map))
    const params: { [key: string]: string } = {
        bbox: map.getBounds().toBBoxString(),
        layer: layerData.layerId,
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
    iframe.width = "425"
    iframe.height = "350"
    iframe.src = `${window.location.origin}/export/embed.html?${qsEncode(params)}`
    iframe.style.border = "1px solid black"

    // allow-popups: allow links to open in a new window: "Report a problem", copyright
    // allow-popups-to-escape-sandbox: opened links should not be restricted by this sandbox
    // allow-scripts: allow the iframe to run javascript
    iframe.setAttribute("sandbox", "allow-popups allow-popups-to-escape-sandbox allow-scripts")
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
 * @example
 * getMapGeoUri(map)
 * // => "geo:51.505,-0.09?z=15"
 */
export const getMapGeoUri = (map: L.Map): string => {
    const { lon, lat, zoom } = getMapState(map)
    const precision = zoomPrecision(zoom)
    const lonFixed = lon.toFixed(precision)
    const latFixed = lat.toFixed(precision)
    return `geo:${latFixed},${lonFixed}?z=${zoom}`
}

/** Clone a tile layer */
export const cloneTileLayer = (layer: L.TileLayer): L.TileLayer => {
    // @ts-ignore
    return new L.TileLayer(layer._url, layer.options)
}

/** Add a control group to the map */
export const addControlGroup = (map: L.Map, controls: L.Control[]): void => {
    for (const control of controls) {
        map.addControl(control)

        const container = control.getContainer()
        const classList = container.classList
        classList.add("leaflet-control-group")

        if (control === controls[0]) classList.add("first")
        if (control === controls[controls.length - 1]) classList.add("last")
    }
}

/** Disable click propagation for map controls, to avoid map events being triggered by the controls */
export const disableControlsClickPropagation = (map: L.Map): void => {
    const mapContainer = map.getContainer()
    const controlContainer = mapContainer.querySelector(".leaflet-control-container") as HTMLElement
    if (controlContainer) {
        console.debug("Disabled click propagation for map controls")
        L.DomEvent.disableClickPropagation(controlContainer)
    } else {
        console.warn("Leaflet control container not found")
    }

    const mapAlertsContainer = mapContainer.querySelectorAll("div.map-alert")
    for (const mapAlert of mapAlertsContainer) {
        L.DomEvent.disableClickPropagation(mapAlert)
    }
    console.debug("Disabled click propagation for", mapAlertsContainer.length, "map alerts")
}

/** Get the map alert element */
export const getMapAlert = (name: string): HTMLElement => {
    const alert = document.querySelector(`.map-alert.${name}`) as HTMLElement
    if (!alert) console.error("Map alert", name, "not found")
    return alert
}
