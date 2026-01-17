import { config } from "@lib/config"
import {
  beautifyZoom,
  isLatitude,
  isLongitude,
  isZoom,
  wrapLongitude,
  zoomPrecision,
} from "@lib/coords"
import { getTimezoneName } from "@lib/format"
import { mapStateStorage } from "@lib/local-storage"
import { qsEncode, qsParse } from "@lib/qs"
import { shortLinkEncode } from "@lib/shortlink"
import { timezoneBoundsMap } from "@lib/timezone-bbox"
import type { Bounds } from "@lib/types"
import { modulo } from "@std/math/modulo"
import { t } from "i18next"
import {
  type EaseToOptions,
  type LngLat,
  LngLatBounds,
  type Map as MaplibreMap,
} from "maplibre-gl"
import { boundsPadding, boundsToString } from "./bounds"
import {
  addMapLayer,
  DEFAULT_LAYER_CODE,
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
  layersCode: string
}

export const getMapLayersCode = (map: MaplibreMap) => {
  const layerCodes = new Set<LayerCode>()
  for (const extendedLayerId of map.getLayersOrder()) {
    const layerId = resolveExtendedLayerId(extendedLayerId)
    const layerConfig = layersConfig.get(layerId)
    if (layerConfig?.layerCode) layerCodes.add(layerConfig.layerCode)
  }
  return Array.from(layerCodes).sort().join("")
}

const setMapLayersCode = (map: MaplibreMap, layersCode?: string) => {
  console.debug("MapState: Setting layers", layersCode)
  const addLayerCodes = new Set<LayerCode>()
  let hasBaseLayer = false

  for (const layerCode of (layersCode ?? "") as Iterable<LayerCode>) {
    const layerId = resolveLayerCodeOrId(layerCode)
    if (!layerId) continue
    addLayerCodes.add(layerCode)
    if (layersConfig.get(layerId)!.isBaseLayer) {
      if (hasBaseLayer) {
        console.error(
          "MapState: Invalid layers code (multiple base layers)",
          layersCode,
        )
        return
      }
      hasBaseLayer = true
    }
  }

  // Add default base layer if no base layer is present
  if (!hasBaseLayer) addLayerCodes.add(DEFAULT_LAYER_CODE)

  // Remove layers not found in the code
  const missingLayerCodes = new Set(addLayerCodes)
  for (const extendedLayerId of map.getLayersOrder()) {
    const layerId = resolveExtendedLayerId(extendedLayerId)
    if (!layerId) continue
    const layerCode = layersConfig.get(layerId)!.layerCode
    if (layerCode === undefined || addLayerCodes.has(layerCode)) {
      if (layerCode !== undefined) missingLayerCodes.delete(layerCode)
      continue
    }
    removeMapLayer(map, layerId)
  }

  // Add missing layers
  for (const layerCode of missingLayerCodes) {
    addMapLayer(map, resolveLayerCodeOrId(layerCode)!)
  }
}

export const getMapState = (map: MaplibreMap): MapState => {
  const { lng, lat } = map.getCenter().wrap()
  const zoom = map.getZoom()
  const layersCode = getMapLayersCode(map)
  return { lon: lng, lat, zoom, layersCode }
}

export const applyMapState = (
  map: MaplibreMap,
  state: MapState,
  options?: EaseToOptions,
) => {
  console.debug("MapState: Setting", state)
  const { lon, lat, zoom, layersCode } = state
  map.panTo([lon, lat], { ...options, zoom })
  setMapLayersCode(map, layersCode)
}

/**
 * Create a hash string for a map state
 * @example
 * encodeMapState(state)
 * // => "#map=15/51.505/-0.09&layers=BT"
 */
export const encodeMapState = (state: MapState | LonLatZoom, prefix = "#map=") => {
  let { lon, lat, zoom } = state
  lon = wrapLongitude(lon)

  const zoomRounded = beautifyZoom(zoom)
  const precision = zoomPrecision(zoom)
  const lonFixed = lon.toFixed(precision)
  const latFixed = lat.toFixed(precision)
  let out = `${prefix}${zoomRounded}/${latFixed}/${lonFixed}`

  const layersCode = "layersCode" in state ? state.layersCode : undefined
  if (layersCode) out += `&layers=${layersCode}`

  return out
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
  const lonLatZoom = parseLonLatZoom(params.map)
  return lonLatZoom ? { ...lonLatZoom, layersCode: params.layers ?? "" } : null
}

export const parseLonLatZoom = (
  input: string | Record<string, string> | undefined,
): LonLatZoom | null => {
  if (!input) return null

  if (typeof input === "object") {
    if (input.at) input = input.at
    else if (input.map) input = input.map
  }

  if (typeof input === "string") {
    const components = input.split("/")
    if (components.length !== 3) return null
    input = {
      zoom: components[0],
      lat: components[1],
      lon: components[2],
    }
  }

  const zoom = Number.parseFloat(input.zoom)
  const lat = Number.parseFloat(input.lat)
  const lon = Number.parseFloat(input.lon)
  return isZoom(zoom) && isLatitude(lat) && isLongitude(lon) ? { lon, lat, zoom } : null
}

const convertBoundsToLonLatZoom = (
  map: MaplibreMap | null | undefined,
  bounds: Bounds,
): LonLatZoom => {
  const [minLon, minLat, maxLon, maxLat] = bounds
  const lon = (minLon + maxLon) / 2
  const lat = (minLat + maxLat) / 2

  if (map) {
    const camera = map.cameraForBounds([minLon, minLat, maxLon, maxLat])
    if (camera?.zoom !== undefined) {
      return { lon, lat, zoom: camera.zoom }
    }
  }

  const latRad = (lat: number) => Math.sin((lat * Math.PI) / 180)
  const getZoom = (mapPx: number, worldPx: number, fraction: number) =>
    (Math.log(mapPx / worldPx / fraction) / Math.LN2) | 0

  // Calculate the fraction of the world that the longitude and latitude take up
  const latFraction = (latRad(maxLat) - latRad(minLat)) / Math.PI
  const lonFraction = modulo(maxLon - minLon, 360) / 360

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

/** Get default map state by analyzing various parameters */
export const getInitialMapState = (map?: MaplibreMap): MapState => {
  const hashState = parseMapState(window.location.hash)

  // 1. Use the position from the hash state
  if (hashState) {
    console.debug("MapState: Initial from hash", hashState)
    return hashState
  }

  // Delay search parsing, most URLs have a valid hash state
  const searchParams = qsParse(window.location.search)
  const lastState = mapStateStorage.get()
  const lastLayersCode = lastState?.layersCode ?? ""

  // 2. Use the bounds from the bbox query parameter
  if (searchParams.bbox) {
    const bbox = searchParams.bbox.split(",").map(Number.parseFloat)
    if (bbox.length === 4 && bbox.every(Number.isFinite)) {
      const { lon, lat, zoom } = convertBoundsToLonLatZoom(map, bbox as Bounds)
      const state = { lon, lat, zoom, layersCode: lastLayersCode }
      console.debug("MapState: Initial from bbox query", state)
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
      const state = { lon, lat, zoom, layersCode: lastLayersCode }
      console.debug("MapState: Initial from bounds query", state)
      return state
    }
  }

  // 4. Use the position from the marker
  if (searchParams.mlon && searchParams.mlat) {
    const mlon = Number.parseFloat(searchParams.mlon)
    const mlat = Number.parseFloat(searchParams.mlat)
    const zoom = searchParams.zoom ? Number.parseFloat(searchParams.zoom) : 12
    if (isLongitude(mlon) && isLatitude(mlat) && isZoom(zoom)) {
      const state = { lon: mlon, lat: mlat, zoom, layersCode: lastLayersCode }
      console.debug("MapState: Initial from marker", state)
      return state
    }
  }

  // 5. Use the position from search parameters
  searchParams.zoom ??= "12"
  const at = parseLonLatZoom(searchParams)
  if (at) {
    const state = { ...at, layersCode: lastLayersCode }
    console.debug("MapState: Initial from at", state)
    return state
  }

  // 6. Use the last location from local storage
  if (lastState) {
    console.debug("MapState: Initial from storage", lastState)
    return lastState
  }

  // 7. Use the user home location
  const homePoint = config.userConfig?.homePoint
  if (homePoint) {
    const { lon, lat } = homePoint
    const state = { lon, lat, zoom: 15, layersCode: "" }
    console.debug("MapState: Initial from home", state)
    return state
  }

  // 8. Use the user's country bounds
  let timezoneName = getTimezoneName()
  while (timezoneName) {
    const countryBounds = timezoneBoundsMap.get(timezoneName)
    if (countryBounds) {
      const countryBoundsPadded = boundsPadding(new LngLatBounds(countryBounds), 0.1)
      const [[minLon, minLat], [maxLon, maxLat]] = countryBoundsPadded.toArray()
      const { lon, lat, zoom } = convertBoundsToLonLatZoom(map, [
        minLon,
        minLat,
        maxLon,
        maxLat,
      ])
      const state = { lon, lat, zoom, layersCode: "" }
      console.debug("MapState: Initial from timezone", state)
      return state
    }
    // Iteratively remove the last timezone component
    // e.g. Europe/Warsaw/Example -> Europe/Warsaw -> Europe
    const lastSlash = timezoneName.lastIndexOf("/")
    timezoneName = lastSlash > 0 ? timezoneName.slice(0, lastSlash) : ""
  }

  // 9. Use the default location
  const defaultState = { lon: 0, lat: 30, zoom: 3, layersCode: "" }
  console.debug("MapState: Initial from default", defaultState)
  return defaultState
}

export const getMapUrl = (state: MapState, showMarker = false) => {
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

const SHORT_DOMAINS: Record<string, string> = {
  "openstreetmap.org": "osm.org",
  "openstreetmap.ng": "osm.ng",
}

export const getMapShortlink = (
  state: MapState,
  markerLngLat?: LngLat | null | undefined,
) => {
  const code = shortLinkEncode(state)
  const params: Record<string, string> = {}
  if (state.layersCode) {
    params.layers = state.layersCode
  }
  if (markerLngLat) {
    const precision = zoomPrecision(state.zoom)
    params.mlon = markerLngLat.lng.toFixed(precision)
    params.mlat = markerLngLat.lat.toFixed(precision)
  }

  // Upgrade to short domain when supported
  const hostname = location.hostname
  const tldPos = hostname.lastIndexOf(".")
  const domainPos = hostname.lastIndexOf(".", tldPos - 1)
  const shortDomainKey = domainPos > 0 ? hostname.slice(domainPos + 1) : hostname
  const host = SHORT_DOMAINS[shortDomainKey] ?? location.host

  return `${location.protocol}//${host}/go/${code}${qsEncode(params)}`
}

export const getMapEmbedHtml = (
  state: MapState,
  bounds: LngLatBounds,
  baseLayerId: LayerId,
  markerLngLat: LngLat | null,
) => {
  const params: Record<string, string> = {
    bbox: boundsToString(bounds),
    layer: baseLayerId,
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
  iframe.src = `${window.location.origin}/export/embed.html${qsEncode(params)}`
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
  link.href = getMapUrl(state, Boolean(markerLngLat))
  link.textContent = t("javascripts.share.view_larger_map")
  small.appendChild(link)
  container.appendChild(small)

  return container.innerHTML
}

export const getMapGeoUri = (state: LonLatZoom) => {
  const { lon, lat, zoom } = state
  const precision = zoomPrecision(zoom)
  const lonFixed = lon.toFixed(precision)
  const latFixed = lat.toFixed(precision)
  return `geo:${latFixed},${lonFixed}?z=${Math.round(zoom)}`
}
