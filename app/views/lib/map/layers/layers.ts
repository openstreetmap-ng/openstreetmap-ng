import { overlayOpacityStorage } from "@lib/local-storage"
import { effectiveTheme } from "@lib/theme"
import libertyStyle from "@lib/vector-styles/liberty.json"
import { batch, effect, signal } from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import { filterKeys } from "@std/collections/filter-keys"
import type { FeatureCollection } from "geojson"
import { t } from "i18next"
import {
  type AddLayerObject,
  type FilterSpecification,
  type LayerSpecification,
  type Map as MaplibreMap,
  RasterTileSource,
  type SourceSpecification,
  type StyleSpecification,
} from "maplibre-gl"

declare const brandSymbol: unique symbol

export type LayerId = string & { readonly [brandSymbol]: unique symbol }
export type LayerCode = string & { readonly [brandSymbol]: unique symbol }

export const STANDARD_LAYER_ID = "standard" as LayerId
export const DEFAULT_LAYER_ID = STANDARD_LAYER_ID
export const DEFAULT_LAYER_CODE = "" as LayerCode

export const LIBERTY_LAYER_ID = "liberty" as LayerId
export const CYCLOSM_LAYER_ID = "cyclosm" as LayerId
export const CYCLEMAP_LAYER_ID = "cyclemap" as LayerId
export const TRANSPORTMAP_LAYER_ID = "transportmap" as LayerId
export const TRACESTRACKTOPO_LAYER_ID = "tracestracktopo" as LayerId
export const HOT_LAYER_ID = "hot" as LayerId

export const LIBERTY_LAYER_CODE = "L" as LayerCode
export const CYCLOSM_LAYER_CODE = "Y" as LayerCode
export const CYCLEMAP_LAYER_CODE = "C" as LayerCode
export const TRANSPORTMAP_LAYER_CODE = "T" as LayerCode
export const TRACESTRACKTOPO_LAYER_CODE = "P" as LayerCode
export const HOT_LAYER_CODE = "H" as LayerCode

export const AERIAL_LAYER_ID = "aerial" as LayerId
export const NOTES_LAYER_ID = "notes" as LayerId
export const DATA_LAYER_ID = "data" as LayerId
export const GPS_LAYER_ID = "gps" as LayerId

export const AERIAL_LAYER_CODE = "A" as LayerCode
export const NOTES_LAYER_CODE = "N" as LayerCode
export const DATA_LAYER_CODE = "D" as LayerCode
export const GPS_LAYER_CODE = "G" as LayerCode

const HIGH_RES_TILES = window.devicePixelRatio > 1
const THUNDERFOREST_API_KEY = "9b990c27013343a99536213faee0983e"
const TRACESTRACK_API_KEY = "684615014d1a572361803e062ccf609a"

const copyrightText = t("javascripts.map.openstreetmap_contributors")
const copyright = `© <a href="/copyright" rel="license" target="_blank">${copyrightText}</a>`
const termsText = t("javascripts.map.website_and_api_terms")
const terms = `<a href="https://osmfoundation.org/wiki/Terms_of_Use" rel="terms-of-service" target="_blank">${termsText}</a>`
const donateTitle = t("layouts.make_a_donation.title")
const donateText = t("layouts.make_a_donation.text")
const osmFranceText = t("javascripts.map.osm_france")
const osmFranceLink = `<a href="https://www.openstreetmap.fr" target="_blank">${osmFranceText}</a>`
const cyclosmText = t("javascripts.map.cyclosm_name")
const cyclosmLink = `<a href="https://www.cyclosm.org" target="_blank">${cyclosmText}</a>`
const cyclosmCredit = t("javascripts.map.cyclosm_credit", {
  cyclosm_link: cyclosmLink,
  osm_france_link: osmFranceLink,
  interpolation: { escapeValue: false },
})
const thunderforestText = t("javascripts.map.andy_allan")
const thunderforestLink = `<a href="https://www.thunderforest.com" target="_blank">${thunderforestText}</a>`
const thunderforestCredit = t("javascripts.map.thunderforest_credit", {
  thunderforest_link: thunderforestLink,
  interpolation: { escapeValue: false },
})
const tracestrackText = t("javascripts.map.tracestrack")
const tracestrackLink = `<a href="https://www.tracestrack.com" target="_blank">${tracestrackText}</a>`
const tracestrackCredit = t("javascripts.map.tracestrack_credit", {
  tracestrack_link: tracestrackLink,
  interpolation: { escapeValue: false },
})
const hotosmText = t("javascripts.map.hotosm_name")
const hotosmLink = `<a href="https://www.hotosm.org" target="_blank">${hotosmText}</a>`
const hotosmCredit = t("javascripts.map.hotosm_credit", {
  hotosm_link: hotosmLink,
  osm_france_link: osmFranceLink,
  interpolation: { escapeValue: false },
})

// https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9
// https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/0
const aerialEsriCredit =
  "Esri, Maxar, Earthstar Geographics, and the GIS User Community"

export const emptyFeatureCollection: FeatureCollection = {
  type: "FeatureCollection",
  features: [],
}

export type AddMapLayerOptions = Omit<
  LayerSpecification,
  "id" | "type" | "source" | "filter"
>

interface LayerConfig {
  specification: SourceSpecification
  vectorStyle?: StyleSpecification
  darkTiles?: RasterTileSource["tiles"]
  isBaseLayer?: boolean
  layerCode?: LayerCode
  legacyLayerIds?: LayerId[]
  layerTypes?: LayerType[]
  layerOptions?: AddMapLayerOptions
  /** Layers with higher priority are drawn on top of others, defaults to 0 */
  priority?: number
}

export const layersConfig = new Map<LayerId, LayerConfig>()

layersConfig.set(STANDARD_LAYER_ID, {
  specification: {
    type: "raster",
    maxzoom: 19,
    tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
    tileSize: 256,
    attribution: `${copyright} ♥ <a class="donate" href="https://supporting.openstreetmap.org" target="_blank" title="${donateTitle}">${donateText}</a>. ${terms}`,
  },
  isBaseLayer: true,
  layerCode: DEFAULT_LAYER_CODE,
  legacyLayerIds: ["mapnik"] as LayerId[],
})

layersConfig.set(LIBERTY_LAYER_ID, {
  specification: { type: "vector" },
  // @ts-expect-error
  vectorStyle: libertyStyle,
  isBaseLayer: true,
  layerCode: LIBERTY_LAYER_CODE,
})

layersConfig.set(CYCLOSM_LAYER_ID, {
  specification: {
    type: "raster",
    maxzoom: 20,
    // oxlint-disable-next-line unicorn/prefer-spread
    tiles: "abc"
      .split("")
      .map((c) => `https://${c}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png`),
    tileSize: 256,
    attribution: `${copyright}. ${cyclosmCredit}. ${terms}`,
  },
  isBaseLayer: true,
  layerCode: CYCLOSM_LAYER_CODE,
})

layersConfig.set(CYCLEMAP_LAYER_ID, {
  specification: {
    type: "raster",
    maxzoom: 21,
    tiles: [
      `https://tile.thunderforest.com/cycle/{z}/{x}/{y}${HIGH_RES_TILES ? "@2x" : ""}.png?apikey=${THUNDERFOREST_API_KEY}`,
    ],
    tileSize: 256,
    attribution: `${copyright}. ${thunderforestCredit}. ${terms}`,
  },
  isBaseLayer: true,
  layerCode: CYCLEMAP_LAYER_CODE,
  legacyLayerIds: ["cycle map"] as LayerId[],
})

layersConfig.set(TRANSPORTMAP_LAYER_ID, {
  specification: {
    type: "raster",
    maxzoom: 21,
    tiles: [
      `https://tile.thunderforest.com/transport/{z}/{x}/{y}${HIGH_RES_TILES ? "@2x" : ""}.png?apikey=${THUNDERFOREST_API_KEY}`,
    ],
    tileSize: 256,
    attribution: `${copyright}. ${thunderforestCredit}. ${terms}`,
  },
  darkTiles: [
    `https://tile.thunderforest.com/transport-dark/{z}/{x}/{y}${HIGH_RES_TILES ? "@2x" : ""}.png?apikey=${THUNDERFOREST_API_KEY}`,
  ],
  isBaseLayer: true,
  layerCode: TRANSPORTMAP_LAYER_CODE,
})

layersConfig.set(TRACESTRACKTOPO_LAYER_ID, {
  specification: {
    type: "raster",
    maxzoom: 19,
    tiles: [
      `https://tile.tracestrack.com/topo__/{z}/{x}/{y}.png?key=${TRACESTRACK_API_KEY}`,
    ],
    tileSize: 256,
    attribution: `${copyright}. ${tracestrackCredit}. ${terms}`,
  },
  isBaseLayer: true,
  layerCode: TRACESTRACKTOPO_LAYER_CODE,
})

layersConfig.set(HOT_LAYER_ID, {
  specification: {
    type: "raster",
    maxzoom: 20,
    // oxlint-disable-next-line unicorn/prefer-spread
    tiles: "abc"
      .split("")
      .map((c) => `https://tile-${c}.openstreetmap.fr/hot/{z}/{x}/{y}.png`),
    tileSize: 256,
    attribution: `${copyright}. ${hotosmCredit}. ${terms}`,
  },
  isBaseLayer: true,
  layerCode: HOT_LAYER_CODE,
})

// Overlay layers
layersConfig.set(AERIAL_LAYER_ID, {
  specification: {
    type: "raster",
    maxzoom: 23,
    tiles: [
      "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    ],
    tileSize: 256,
    attribution: aerialEsriCredit,
  },
  layerOptions: {
    paint: {
      // @ts-expect-error loaded from storage
      "raster-opacity": null,
    },
  },
  layerCode: AERIAL_LAYER_CODE,
  priority: 50,
})

layersConfig.set(GPS_LAYER_ID, {
  specification: {
    type: "raster",
    // This layer has no zoom limits
    tiles: ["https://gps.tile.openstreetmap.org/lines/{z}/{x}/{y}.png"],
    tileSize: 256,
  },
  layerCode: GPS_LAYER_CODE,
  priority: 60,
})

const layerLookupMap = memoize(() => {
  console.debug("Layers: Initializing lookup map", layersConfig.size)
  const result = new Map<LayerId | LayerCode, LayerId>()
  for (const [layerId, config] of layersConfig) {
    result.set(layerId, layerId)
    if (config.layerCode !== undefined) {
      result.set(config.layerCode, layerId)
    }
    if (config.legacyLayerIds) {
      for (const legacyLayerId of config.legacyLayerIds) {
        result.set(legacyLayerId, layerId)
      }
    }
  }
  return result
})

/**
 * Resolve a layer code or id to actual layer id.
 * Returns undefined if no matching layer is found.
 * @example
 * resolveLayerCodeOrId("mapnik")
 * // => "standard"
 */
export const resolveLayerCodeOrId = (layerCodeOrId: LayerCode | LayerId) =>
  layerLookupMap().get(layerCodeOrId)

/**
 * Add layers sources to the map.
 * @param map - Map instance to add sources to
 * @param kind - "all" for all layers, "base" for base layers, or a specific layer id
 */
export const addMapLayerSources = (
  map: MaplibreMap,
  kind: "all" | "base" | LayerId,
) => {
  const exactConfig = layersConfig.get(kind as LayerId)
  const isDarkTheme = effectiveTheme.value === "dark"
  let watchMap = false
  for (const [layerId, config] of exactConfig
    ? [[kind, exactConfig] as [LayerId, LayerConfig]]
    : layersConfig) {
    if (kind === "base" && !config.isBaseLayer) continue
    const specType = config.specification.type
    if (specType === "raster" || specType === "geojson") {
      if (!watchMap && config.darkTiles) watchMap = true
      if (isDarkTheme && config.darkTiles) {
        // @ts-expect-error
        map.addSource(layerId, {
          ...config.specification,
          tiles: config.darkTiles,
        } as RasterTileSource)
      } else {
        map.addSource(layerId, config.specification)
      }
    } else if (specType === "vector") {
      for (const [sourceId, source] of Object.entries(config.vectorStyle!.sources)) {
        if (
          (source.type !== "raster" && source.type !== "vector") ||
          !(source.tiles || source.url)
        )
          continue
        if (source.attribution || config.specification.attribution)
          // @ts-expect-error override source attribution
          source.attribution = config.specification.attribution
        map.addSource(getExtendedLayerId(layerId, sourceId as LayerType), source)
      }
    }
  }
  if (watchMap) watchMapsLayerSources.add(map)
}
const watchMapsLayerSources = new Set<MaplibreMap>()

// Listen for theme changes
effect(() => {
  const isDarkTheme = effectiveTheme.value === "dark"
  console.debug(
    "Layers: Set",
    isDarkTheme ? "dark" : "light",
    "tiles for",
    watchMapsLayerSources.size,
    "maps",
  )
  for (const map of watchMapsLayerSources) {
    for (const [layerId, config] of layersConfig) {
      const source = map.getSource(layerId)
      if (!(source instanceof RasterTileSource && config.darkTiles)) continue

      // @ts-expect-error
      source.setTiles(isDarkTheme ? config.darkTiles : config.specification.tiles)
    }
  }
})

export const getExtendedLayerId = (layerId: LayerId, type: LayerType) =>
  `${layerId}:${type}`

export const resolveExtendedLayerId = (extendedLayerId: string) => {
  const i = extendedLayerId.indexOf(":")
  const layerId = i === -1 ? extendedLayerId : extendedLayerId.slice(0, i)
  return layerId as LayerId
}

type LayerEventHandler = (
  isAdded: boolean,
  layerId: LayerId,
  config: LayerConfig,
) => void

const layerEventHandlers = new Map<symbol, LayerEventHandler>()

/** Add a layer event handler, called when a layer is added or removed */
export const addLayerEventHandler = (handler: LayerEventHandler) => {
  const id = Symbol("layer-event-handler")
  layerEventHandlers.set(id, handler)
  return () => layerEventHandlers.delete(id)
}

export const activeBaseLayerId = signal<LayerId | null>(null)

addLayerEventHandler((isAdded, layerId, config) => {
  if (isAdded && config.isBaseLayer) activeBaseLayerId.value = layerId
})

export type LayerType =
  | "fill"
  | "line"
  | "symbol"
  | "circle"
  | "heatmap"
  | "fill-extrusion"
  | "raster"
  | "hillshade"
  | "background"

const LAYER_TYPE_FILTERS: Partial<Record<LayerType, FilterSpecification>> = {
  fill: ["==", ["geometry-type"], "Polygon"],
  line: ["==", ["geometry-type"], "LineString"],
  circle: ["==", ["geometry-type"], "Point"],
  symbol: ["==", ["geometry-type"], "Point"],
}

export const addMapLayer = (
  map: MaplibreMap,
  layerId: LayerId,
  triggerEvent = true,
) => {
  const config = layersConfig.get(layerId)
  if (!config) {
    console.warn("Layers: Layer not found", layerId)
    return
  }

  const specType = config.specification.type
  let layerTypes!: LayerType[]
  if (config.layerTypes) {
    layerTypes = config.layerTypes
  } else if (specType === "raster") {
    layerTypes = ["raster"]
  } else if (specType !== "vector") {
    console.warn("Layers: Unsupported spec type", specType, layerId)
    return
  }

  const priority = config.priority ?? 0
  const beforeId: string | undefined = map
    .getLayersOrder()
    .find(
      (id) => priority < (layersConfig.get(resolveExtendedLayerId(id))?.priority ?? 0),
    )

  if (specType === "vector") {
    console.debug("Layers: Adding vector", layerId, "before", beforeId)
    const vectorStyle = config.vectorStyle!

    // Add glyphs
    if (vectorStyle.glyphs) map.setGlyphs(vectorStyle.glyphs)

    // Add sprites
    if (Array.isArray(vectorStyle.sprite)) {
      const addedIds = new Set(map.getSprite().map(({ id }) => id))
      for (const { id, url } of vectorStyle.sprite) {
        if (addedIds.has(id)) map.removeSprite(id) // override existing sprites
        map.addSprite(id, url)
      }
    } else if (vectorStyle.sprite) {
      map.setSprite(vectorStyle.sprite)
    }

    // Add layers
    for (const layer of vectorStyle.layers) {
      const layerObject: AddLayerObject = {
        ...layer,
        id: getExtendedLayerId(layerId, layer.id as LayerType),
      }
      // @ts-expect-error
      if (layer.source)
        // @ts-expect-error
        layerObject.source = getExtendedLayerId(
          layerId,
          // @ts-expect-error
          layer.source as LayerType,
        )
      map.addLayer(layerObject, beforeId)
    }
  } else {
    console.debug("Layers: Adding", layerId, layerTypes, "before", beforeId)
    const layerOptions = config.layerOptions ?? {}

    // Override opacity from storage for overlay layers
    if (
      !config.isBaseLayer &&
      layerOptions.paint &&
      "raster-opacity" in layerOptions.paint
    )
      layerOptions.paint["raster-opacity"] = overlayOpacityStorage(layerId).value

    for (const type of layerTypes) {
      const layerObject: AddLayerObject = {
        ...layerOptions,
        id: layerId,
        // @ts-expect-error
        type: type as string,
        // @ts-expect-error
        source: layerId,
      }
      if (layerTypes.length > 1) {
        layerObject.id = getExtendedLayerId(layerId, type)

        // Remove unsupported layer options
        const validPrefixes = [`${type}-`]
        if (type === "symbol") validPrefixes.push("icon-", "text-")

        const hasValidPrefix = (key: string) =>
          validPrefixes.some((prefix) => key.startsWith(prefix))

        for (const key of ["layout", "paint"] as const) {
          const value = layerOptions[key]
          if (!value) continue

          // @ts-expect-error
          layerObject[key] = filterKeys(
            value as Record<string, unknown>,
            hasValidPrefix,
          )
        }
      }
      const filter = LAYER_TYPE_FILTERS[type]
      // @ts-expect-error
      if (filter) layerObject.filter = filter
      map.addLayer(layerObject, beforeId)
    }
  }

  if (triggerEvent) {
    batch(() => {
      for (const handler of layerEventHandlers.values()) {
        handler(true, layerId, config)
      }
    })
  }
}

export const removeMapLayer = (
  map: MaplibreMap,
  layerId: LayerId,
  triggerEvent = true,
) => {
  let removed = false
  // Remove layers
  for (const extendedLayerId of map.getLayersOrder()) {
    if (resolveExtendedLayerId(extendedLayerId) !== layerId) continue
    console.debug("Layers: Removing", extendedLayerId, "for", layerId)
    map.removeLayer(extendedLayerId)
    removed = true
  }
  if (removed) {
    const config = layersConfig.get(layerId)!

    if (config.specification.type === "vector") {
      const vectorStyle = config.vectorStyle!

      // Remove glyphs
      if (vectorStyle.glyphs) map.setGlyphs(null)

      // Remove sprites
      if (Array.isArray(vectorStyle.sprite)) {
        for (const { id } of vectorStyle.sprite) {
          map.removeSprite(id)
        }
      } else if (vectorStyle.sprite) {
        map.setSprite(null)
      }
    }

    if (triggerEvent) {
      batch(() => {
        for (const handler of layerEventHandlers.values()) {
          handler(false, layerId, config)
        }
      })
    }
  } else {
    console.debug("Layers: Nothing to remove", layerId)
  }
}

/** Test if a layer is present in the map */
export const hasMapLayer = (map: MaplibreMap, layerId: LayerId) => {
  for (const extendedLayerId of map.getLayersOrder()) {
    if (resolveExtendedLayerId(extendedLayerId) === layerId) return true
  }
  return false
}
