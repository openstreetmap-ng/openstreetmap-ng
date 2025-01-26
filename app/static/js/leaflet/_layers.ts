import type { FeatureCollection } from "geojson"
import i18next from "i18next"
import type {
    AddLayerObject,
    FilterSpecification,
    LayerSpecification,
    Map as MaplibreMap,
    SourceSpecification,
} from "maplibre-gl"
import { getMapOverlayOpacity } from "../_local-storage.ts"
import { getDeviceTheme, staticCache } from "../_utils.ts"

declare const brandSymbol: unique symbol

export type LayerId = string & { readonly [brandSymbol]: unique symbol }
export type LayerCode = string & { readonly [brandSymbol]: unique symbol }

const thunderforestApiKey: string = "9b990c27013343a99536213faee0983e"
const tracestrackApiKey: string = "684615014d1a572361803e062ccf609a"

const copyrightText = i18next.t("javascripts.map.openstreetmap_contributors")
const copyright = `© <a href="/copyright" rel="license" target="_blank">${copyrightText}</a>`
const termsText = i18next.t("javascripts.map.website_and_api_terms")
const terms = `<a href="https://osmfoundation.org/wiki/Terms_of_Use" rel="terms-of-service" target="_blank">${termsText}</a>`
const donateTitle = i18next.t("layouts.make_a_donation.title")
const donateText = i18next.t("layouts.make_a_donation.text")
const osmFranceText = i18next.t("javascripts.map.osm_france")
const osmFranceLink = `<a href="https://www.openstreetmap.fr" target="_blank">${osmFranceText}</a>`
const cyclosmText = i18next.t("javascripts.map.cyclosm_name")
const cyclosmLink = `<a href="https://www.cyclosm.org" target="_blank">${cyclosmText}</a>`
const cyclosmCredit = i18next.t("javascripts.map.cyclosm_credit", {
    cyclosm_link: cyclosmLink,
    osm_france_link: osmFranceLink,
    interpolation: { escapeValue: false },
})
const thunderforestText = i18next.t("javascripts.map.andy_allan")
const thunderforestLink = `<a href="https://www.thunderforest.com" target="_blank">${thunderforestText}</a>`
const thunderforestCredit = i18next.t("javascripts.map.thunderforest_credit", {
    thunderforest_link: thunderforestLink,
    interpolation: { escapeValue: false },
})
const tracestrackText = i18next.t("javascripts.map.tracestrack")
const tracestrackLink = `<a href="https://www.tracestrack.com" target="_blank">${tracestrackText}</a>`
const tracestrackCredit = i18next.t("javascripts.map.tracestrack_credit", {
    tracestrack_link: tracestrackLink,
    interpolation: { escapeValue: false },
})
const hotosmText = i18next.t("javascripts.map.hotosm_name")
const hotosmLink = `<a href="https://www.hotosm.org" target="_blank">${hotosmText}</a>`
const hotosmCredit = i18next.t("javascripts.map.hotosm_credit", {
    hotosm_link: hotosmLink,
    osm_france_link: osmFranceLink,
    interpolation: { escapeValue: false },
})

// https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9
// https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/0
const aerialEsriCredit = "Esri, Maxar, Earthstar Geographics, and the GIS User Community"

export const emptyFeatureCollection: FeatureCollection = {
    type: "FeatureCollection",
    features: [],
}

export type AddMapLayerOptions = Omit<LayerSpecification, "id" | "type" | "source" | "filter">

interface LayerConfig {
    specification: SourceSpecification
    isBaseLayer?: boolean
    layerCode?: LayerCode
    legacyLayerIds?: LayerId[]
    layerTypes?: LayerType[]
    layerOptions?: AddMapLayerOptions
    /** Layers with higher priority are drawn on top of others, defaults to 0. */
    priority?: number
}

export const layersConfig = new Map<LayerId, LayerConfig>()

layersConfig.set("standard" as LayerId, {
    specification: {
        type: "raster",
        maxzoom: 19,
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        attribution: `${copyright} ♥ <a class="donate" href="https://supporting.openstreetmap.org" target="_blank" title="${donateTitle}">${donateText}</a>. ${terms}`,
    },
    isBaseLayer: true,
    layerCode: "" as LayerCode,
    legacyLayerIds: ["mapnik"] as LayerId[],
})

layersConfig.set("cyclosm" as LayerId, {
    specification: {
        type: "raster",
        maxzoom: 20,
        tiles: "abc".split("").map((c) => `https://${c}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png`),
        tileSize: 256,
        attribution: `${copyright}. ${cyclosmCredit}. ${terms}`,
    },
    isBaseLayer: true,
    layerCode: "Y" as LayerCode,
})

layersConfig.set("cyclemap" as LayerId, {
    specification: {
        type: "raster",
        maxzoom: 21,
        tiles: [`https://tile.thunderforest.com/cycle/{z}/{x}/{y}.png?apikey=${thunderforestApiKey}`],
        tileSize: 256,
        attribution: `${copyright}. ${thunderforestCredit}. ${terms}`,
    },
    isBaseLayer: true,
    layerCode: "C" as LayerCode,
    legacyLayerIds: ["cycle map"] as LayerId[],
})

// TODO: would be nice to support changing in runtime
layersConfig.set("transportmap" as LayerId, {
    specification: {
        type: "raster",
        maxzoom: 21,
        tiles: [
            `https://tile.thunderforest.com/transport${getDeviceTheme() === "dark" ? "-dark" : ""}/{z}/{x}/{y}.png?apikey=${thunderforestApiKey}`,
        ],
        tileSize: 256,
        attribution: `${copyright}. ${thunderforestCredit}. ${terms}`,
    },
    isBaseLayer: true,
    layerCode: "T" as LayerCode,
})

layersConfig.set("tracestracktopo" as LayerId, {
    specification: {
        type: "raster",
        maxzoom: 19,
        tiles: [`https://tile.tracestrack.com/topo__/{z}/{x}/{y}.png?key=${tracestrackApiKey}`],
        tileSize: 256,
        attribution: `${copyright}. ${tracestrackCredit}. ${terms}`,
    },
    isBaseLayer: true,
    layerCode: "P" as LayerCode,
})

layersConfig.set("hot" as LayerId, {
    specification: {
        type: "raster",
        maxzoom: 20,
        tiles: "abc".split("").map((c) => `https://tile-${c}.openstreetmap.fr/hot/{z}/{x}/{y}.png`),
        tileSize: 256,
        attribution: `${copyright}. ${hotosmCredit}. ${terms}`,
    },
    isBaseLayer: true,
    layerCode: "H" as LayerCode,
})

// Overlay layers
layersConfig.set("aerial" as LayerId, {
    specification: {
        type: "raster",
        maxzoom: 23,
        tiles: ["https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
        tileSize: 256,
        attribution: aerialEsriCredit,
    },
    layerOptions: {
        paint: {
            "raster-opacity": getMapOverlayOpacity("aerial"),
        },
    },
    layerCode: "A" as LayerCode,
    priority: 50,
})

layersConfig.set("gps" as LayerId, {
    specification: {
        type: "raster",
        // This layer has no zoom limits
        tiles: ["https://gps.tile.openstreetmap.org/lines/{z}/{x}/{y}.png"],
        tileSize: 256,
    },
    layerCode: "G" as LayerCode,
    priority: 60,
})

const layerLookupMap = staticCache((): Map<LayerId | LayerCode, LayerId> => {
    console.debug("Lazily initializing layerLookupMap with", layersConfig.size, "configured layers")
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
export const resolveLayerCodeOrId = (layerCodeOrId: LayerCode | LayerId): LayerId | undefined =>
    layerLookupMap().get(layerCodeOrId)

export const defaultLayerId = "standard" as LayerId

/** Add layers sources to the map. */
export const addMapLayerSources = (map: MaplibreMap, kind: "base" | "all"): void => {
    for (const [layerId, config] of layersConfig) {
        if (kind === "all" || config.isBaseLayer) {
            map.addSource(layerId, config.specification)
        }
    }
}

export const getExtendedLayerId = (layerId: LayerId, type: LayerType): string => `${layerId}:${type}`

export const resolveExtendedLayerId = (extendedLayerId: string): LayerId => {
    const i = extendedLayerId.indexOf(":")
    const layerId = i === -1 ? extendedLayerId : extendedLayerId.slice(0, i)
    return layerId as LayerId
}

type LayerEventHandler = (isAdded: boolean, layerId: LayerId, config: LayerConfig) => void

const layerEventHandlers: LayerEventHandler[] = []

/** Add a layer event handler, called when a layer is added or removed */
export const addLayerEventHandler = (handler: LayerEventHandler): void => {
    layerEventHandlers.push(handler)
}

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

const layerTypeFilters = Object.freeze({
    fill: ["==", ["geometry-type"], "Polygon"],
    line: ["==", ["geometry-type"], "LineString"],
    circle: ["==", ["geometry-type"], "Point"],
    symbol: ["==", ["geometry-type"], "Point"],
}) as Record<LayerType, FilterSpecification>

export const addMapLayer = (map: MaplibreMap, layerId: LayerId, triggerEvent = true): void => {
    const config = layersConfig.get(layerId)
    if (!config) {
        console.warn("Layer", layerId, "not found in", layersConfig.keys())
        return
    }

    const specType = config.specification.type
    let layerTypes: LayerType[]
    if (config.layerTypes) {
        layerTypes = config.layerTypes
    } else if (specType === "raster") {
        layerTypes = ["raster"]
    } else {
        console.warn("Unsupported specification type", specType, "on layer", layerId)
        return
    }

    const priority = config.priority ?? 0
    const beforeId: string | undefined = map
        .getLayersOrder()
        .find((id) => priority < (layersConfig.get(resolveExtendedLayerId(id))?.priority ?? 0))

    console.debug("Adding layer", layerId, "with types", layerTypes, "before", beforeId)
    const layerOptions = config.layerOptions ?? {}
    for (const type of layerTypes) {
        const layerObject: AddLayerObject = {
            ...layerOptions,
            // @ts-ignore
            type: type as string,
            // @ts-ignore
            source: layerId,
        }
        if (layerTypes.length > 1) {
            layerObject.id = getExtendedLayerId(layerId, type)
            // Remove unsupported layer options
            const validPrefixes = [`${type}-`]
            if (type === "symbol") validPrefixes.push("icon-", "text-")
            for (const key of ["layout", "paint"] as const) {
                const value = layerOptions[key]
                if (!value) continue
                const newValue: Record<string, unknown> = {}
                for (const [k, v] of Object.entries(value)) {
                    for (const prefix of validPrefixes) {
                        if (!k.startsWith(prefix)) continue
                        newValue[k] = v
                    }
                }
                // @ts-ignore
                layerObject[key] = newValue
            }
        } else {
            layerObject.id = layerId
        }
        const filter = layerTypeFilters[type]
        // @ts-ignore
        if (filter) layerObject.filter = filter
        map.addLayer(layerObject, beforeId)
    }
    if (triggerEvent) {
        for (const handler of layerEventHandlers) {
            handler(true, layerId, config)
        }
    }
}

export const removeMapLayer = (map: MaplibreMap, layerId: LayerId, triggerEvent = true): void => {
    let removed = false
    for (const extendedLayerId of map.getLayersOrder()) {
        if (resolveExtendedLayerId(extendedLayerId) !== layerId) continue
        console.debug("Removing layer", extendedLayerId, "because of", layerId)
        map.removeLayer(extendedLayerId)
        removed = true
    }
    if (removed) {
        if (triggerEvent) {
            const config = layersConfig.get(layerId)
            for (const handler of layerEventHandlers) {
                handler(false, layerId, config)
            }
        }
    } else {
        console.debug("Removed no layers with id", layerId)
    }
}

/** Test if a layer is present in the map */
export const hasMapLayer = (map: MaplibreMap, layerId: LayerId): boolean => {
    for (const extendedLayerId of map.getLayersOrder()) {
        if (resolveExtendedLayerId(extendedLayerId) === layerId) return true
    }
    return false
}
