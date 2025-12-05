import { config } from "@lib/config"
import {
    beautifyZoom,
    isLatitude,
    isLongitude,
    isZoom,
    zoomPrecision,
} from "@lib/coords"
import { getTimezoneName } from "@lib/format"
import { mapStateStorage } from "@lib/local-storage"
import { qsEncode, qsParse } from "@lib/qs"
import { shortLinkEncode } from "@lib/shortlink"
import { timezoneBoundsMap } from "@lib/timezone-bbox"
import type { Bounds } from "@lib/types"
import { mod } from "@lib/utils"
import i18next from "i18next"
import {
    type EaseToOptions,
    type LngLat,
    LngLatBounds,
    type Map as MaplibreMap,
} from "maplibre-gl"
import { padLngLatBounds } from "./bounds"
import {
    addMapLayer,
    type LayerCode,
    type LayerId,
    layersConfig,
    removeMapLayer,
    resolveExtendedLayerId,
    resolveLayerCodeOrId,
} from "./layers/layers"

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
export const getMapLayersCode = (map: MaplibreMap): string => {
    const layerCodes = new Set<LayerCode>()
    for (const extendedLayerId of map.getLayersOrder()) {
        const layerId = resolveExtendedLayerId(extendedLayerId)
        const layerConfig = layersConfig.get(layerId)
        if (layerConfig?.layerCode) layerCodes.add(layerConfig.layerCode)
    }
    return Array.from(layerCodes).sort().join("")
}

/**
 * Set the map layers from a layers code
 * @example
 * setMapLayersCode(map, "BT")
 */
const setMapLayersCode = (map: MaplibreMap, layersCode?: string): void => {
    console.debug("setMapLayersCode", layersCode)
    const addLayerCodes = new Set<LayerCode>()
    let hasBaseLayer = false

    for (const layerCode of (layersCode || "") as Iterable<LayerCode>) {
        const layerId = resolveLayerCodeOrId(layerCode)
        if (!layerId) continue
        addLayerCodes.add(layerCode)
        if (layersConfig.get(layerId).isBaseLayer) {
            if (hasBaseLayer) {
                console.error(
                    "Invalid layers code",
                    layersCode,
                    "(too many base layers)",
                )
                return
            }
            hasBaseLayer = true
        }
    }

    // Add default base layer if no base layer is present
    if (!hasBaseLayer) addLayerCodes.add("" as LayerCode)

    // Remove layers not found in the code
    const missingLayerCodes = new Set<LayerCode>(addLayerCodes)
    for (const extendedLayerId of map.getLayersOrder()) {
        const layerId = resolveExtendedLayerId(extendedLayerId)
        if (!layerId) continue
        const layerCode = layersConfig.get(layerId).layerCode
        if (layerCode === undefined || addLayerCodes.has(layerCode)) {
            console.debug("Keeping layer", layerId)
            missingLayerCodes.delete(layerCode)
            continue
        }
        removeMapLayer(map, layerId)
    }

    // Add missing layers
    for (const layerCode of missingLayerCodes) {
        addMapLayer(map, resolveLayerCodeOrId(layerCode))
    }
}

/**
 * Get the base layer id of the map
 * @example
 * getMapBaseLayerId(map)
 * // => "standard"
 */
export const getMapBaseLayerId = (map: MaplibreMap): LayerId | null => {
    let baseLayerId: LayerId | null = null
    for (const extendedLayerId of map.getLayersOrder()) {
        const layerId = resolveExtendedLayerId(extendedLayerId)
        const layerConfig = layersConfig.get(layerId)
        if (layerConfig?.isBaseLayer) {
            if (baseLayerId) console.warn("Multiple base layers found")
            baseLayerId = layerId
        }
    }
    return baseLayerId
}

/** Get the current map state object */
export const getMapState = (map: MaplibreMap): MapState => {
    const center = map.getCenter().wrap()
    const zoom = map.getZoom()
    const layersCode = getMapLayersCode(map)
    return { lon: center.lng, lat: center.lat, zoom, layersCode }
}

/** Set the map state from a state object */
export const setMapState = (
    map: MaplibreMap,
    state: MapState,
    options?: EaseToOptions,
): void => {
    console.debug("setMapState", state)
    const { lon, lat, zoom, layersCode } = state
    map.panTo([lon, lat], { ...(options ?? {}), zoom })
    setMapLayersCode(map, layersCode)
    mapStateStorage.set(state)
}

/**
 * Create a hash string for a map state
 * @example
 * encodeMapState(state)
 * // => "#map=15/51.505/-0.09&layers=BT"
 */
export const encodeMapState = (state: MapState): string => {
    let { lon, lat, zoom, layersCode } = state
    lon = mod(lon + 180, 360) - 180
    const zoomRounded = beautifyZoom(zoom)
    const precision = zoomPrecision(zoom)
    const lonFixed = lon.toFixed(precision)
    const latFixed = lat.toFixed(precision)
    return layersCode
        ? `#map=${zoomRounded}/${latFixed}/${lonFixed}&layers=${layersCode}`
        : `#map=${zoomRounded}/${latFixed}/${lonFixed}`
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
    const params = qsParse(hash.substring(i + 1))

    // Hash string must contain map parameter
    if (!params.map) return null

    // Map must contain zoom, lat, lon parameters
    const components = params.map.split("/")
    if (components.length !== 3) return null

    const zoom = Number.parseFloat(components[0])
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
const convertBoundsToLonLatZoom = (
    map: MaplibreMap | null,
    bounds: Bounds,
): LonLatZoom => {
    const [minLon, minLat, maxLon, maxLat] = bounds
    const lon = (minLon + maxLon) / 2
    const lat = (minLat + maxLat) / 2

    if (map) {
        const camera = map.cameraForBounds([minLon, minLat, maxLon, maxLat])
        if (camera) return { lon, lat, zoom: camera.zoom }
    }

    const latRad = (lat: number): number => Math.sin((lat * Math.PI) / 180)
    const getZoom = (mapPx: number, worldPx: number, fraction: number): number =>
        (Math.log(mapPx / worldPx / fraction) / Math.LN2) | 0

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
 * Get default map state by analyzing various parameters
 * @example
 * getInitialMapState()
 * // => { lon: -0.09, lat: 51.505, zoom: 15, layersCode: "BT" }
 */
export const getInitialMapState = (map?: MaplibreMap): MapState => {
    const hashState = parseMapState(window.location.hash)

    // 1. Use the position from the hash state
    if (hashState) {
        console.debug("Initial map state from hash", hashState)
        return hashState
    }

    // Delay search parsing, most URLs have a valid hash state
    const searchParams = qsParse(window.location.search)
    const lastState = mapStateStorage.get()

    // 2. Use the bounds from the bbox query parameter
    if (searchParams.bbox) {
        const bbox = searchParams.bbox.split(",").map(Number.parseFloat)
        if (bbox.length === 4) {
            const { lon, lat, zoom } = convertBoundsToLonLatZoom(map, bbox as Bounds)
            const state = { lon, lat, zoom, layersCode: lastState?.layersCode }
            console.debug("Initial map state from bbox query", state)
            return state
        }
    }

    // 3. Use the bounds from minlon, minlat, maxlon, maxlat query parameters
    if (
        searchParams.minlon &&
        searchParams.minlat &&
        searchParams.maxlon &&
        searchParams.maxlat
    ) {
        const minLon = Number.parseFloat(searchParams.minlon)
        const minLat = Number.parseFloat(searchParams.minlat)
        const maxLon = Number.parseFloat(searchParams.maxlon)
        const maxLat = Number.parseFloat(searchParams.maxlat)
        if (
            isLongitude(minLon) &&
            isLatitude(minLat) &&
            isLongitude(maxLon) &&
            isLatitude(maxLat)
        ) {
            const { lon, lat, zoom } = convertBoundsToLonLatZoom(map, [
                minLon,
                minLat,
                maxLon,
                maxLat,
            ])
            const state = { lon, lat, zoom, layersCode: lastState?.layersCode }
            console.debug("Initial map state from bounds query", state)
            return state
        }
    }

    // 4. Use the position from the marker
    if (searchParams.mlon && searchParams.mlat) {
        const mlon = Number.parseFloat(searchParams.mlon)
        const mlat = Number.parseFloat(searchParams.mlat)
        const zoom = searchParams.zoom ? Number.parseFloat(searchParams.zoom) : 12
        if (isLongitude(mlon) && isLatitude(mlat) && isZoom(zoom)) {
            const state = {
                lon: mlon,
                lat: mlat,
                zoom,
                layersCode: lastState?.layersCode,
            }
            console.debug("Initial map state from marker query", state)
            return state
        }
    }

    // 5. Use the position from lat/lon search parameters
    if (searchParams.lon && searchParams.lat) {
        const lon = Number.parseFloat(searchParams.lon)
        const lat = Number.parseFloat(searchParams.lat)
        const zoom = searchParams.zoom ? Number.parseFloat(searchParams.zoom) : 12
        if (isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
            const state = { lon, lat, zoom, layersCode: lastState?.layersCode }
            console.debug("Initial map state from lon/lat query", state)
            return state
        }
    }

    // 6. Use the last location from local storage
    if (lastState) {
        console.debug("Initial map state from last state", lastState)
        return lastState
    }

    // 7. Use the user home location
    const homePoint = config.userConfig?.homePoint
    if (homePoint) {
        const { lon, lat } = homePoint
        const state = { lon, lat, zoom: 15, layersCode: "" }
        console.debug("Initial map state from home location", state)
        return state
    }

    // 8. Use the user's country bounds
    let timezoneName = getTimezoneName()
    while (timezoneName) {
        const countryBounds = timezoneBoundsMap.get(timezoneName)
        if (countryBounds) {
            const countryBoundsPadded = padLngLatBounds(
                new LngLatBounds(countryBounds),
                0.1,
            )
            const [[minLon, minLat], [maxLon, maxLat]] = countryBoundsPadded.toArray()
            const { lon, lat, zoom } = convertBoundsToLonLatZoom(map, [
                minLon,
                minLat,
                maxLon,
                maxLat,
            ])
            const state = { lon, lat, zoom, layersCode: "" }
            console.debug("Initial map state from country bounds", state)
            return state
        }
        // Iteratively remove the last timezone component
        // e.g. Europe/Warsaw/Example -> Europe/Warsaw -> Europe
        const lastSlash = timezoneName.lastIndexOf("/")
        timezoneName = lastSlash > 0 ? timezoneName.substring(0, lastSlash) : ""
    }

    // 9. Use the default location
    const defaultState = { lon: 0, lat: 30, zoom: 3, layersCode: "" }
    console.debug("Initial map state from default location", defaultState)
    return defaultState
}

/**
 * Get a URL for the current map location
 * @example
 * getMapUrl(map)
 * // => "https://www.openstreetmap.org/#map=15/51.505/-0.09&layers=BT"
 */
export const getMapUrl = (map: MaplibreMap, showMarker = false): string => {
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

const shortDomainUpgrades: Record<string, string> = Object.freeze({
    "openstreetmap.org": "osm.org",
    "openstreetmap.ng": "osm.ng",
})

/**
 * Get a short URL for the current map location
 * @example
 * getMapShortUrl(map)
 * // => "https://osm.org/go/wF7ZdNbjU-"
 */
export const getMapShortlink = (map: MaplibreMap, markerLngLat?: LngLat): string => {
    const state = getMapState(map)
    const code = shortLinkEncode(state)
    const params: { [key: string]: string } = {}
    if (state.layersCode) params.layers = state.layersCode
    if (markerLngLat) {
        const precision = zoomPrecision(state.zoom)
        params.mlon = markerLngLat.lng.toFixed(precision)
        params.mlat = markerLngLat.lat.toFixed(precision)
    }

    // Upgrade to short domain when supported
    const hostname = location.hostname
    const tldPos = hostname.lastIndexOf(".")
    const domainPos = hostname.lastIndexOf(".", tldPos - 1)
    const shortDomainKey = domainPos > 0 ? hostname.substring(domainPos + 1) : hostname
    const host = shortDomainUpgrades[shortDomainKey] ?? location.host

    return Object.keys(params).length
        ? `${location.protocol}//${host}/go/${code}?${qsEncode(params)}`
        : `${location.protocol}//${host}/go/${code}`
}

/**
 * Get HTML for embedding the current map location
 * @example
 * getMapEmbedHtml(map, [-0.09, 51.505])
 */
export const getMapEmbedHtml = (map: MaplibreMap, markerLngLat?: LngLat): string => {
    const [[minLon, minLat], [maxLon, maxLat]] = map
        .getBounds()
        .adjustAntiMeridian()
        .toArray()
    const params: { [key: string]: string } = {
        bbox: `${minLon},${minLat},${maxLon},${maxLat}`,
        layer: getMapBaseLayerId(map),
    }

    // Add optional map marker
    if (markerLngLat) {
        // Intentionally not applying precision on embed markers
        const lon = markerLngLat.lng
        const lat = markerLngLat.lat
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
    iframe.setAttribute(
        "sandbox",
        "allow-popups allow-popups-to-escape-sandbox allow-scripts",
    )
    container.appendChild(iframe)

    // Create new line
    const br = document.createElement("br")
    container.appendChild(br)

    // Create the link to view the larger map
    const small = document.createElement("small")
    const link = document.createElement("a")
    link.href = getMapUrl(map, Boolean(markerLngLat))
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
export const getMapGeoUri = (map: MaplibreMap): string => {
    const { lon, lat, zoom } = getMapState(map)
    const precision = zoomPrecision(zoom)
    const lonFixed = lon.toFixed(precision)
    const latFixed = lat.toFixed(precision)
    return `geo:${latFixed},${lonFixed}?z=${zoom | 0}`
}
