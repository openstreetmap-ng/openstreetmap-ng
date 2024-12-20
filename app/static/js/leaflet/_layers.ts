import i18next from "i18next"
import * as L from "leaflet"
import { getOverlayOpacity } from "../_local-storage"

declare const brandSymbol: unique symbol

export type LayerId = string & { readonly [brandSymbol]: unique symbol }
export type LayerCode = string & { readonly [brandSymbol]: unique symbol }

interface LayerInstanceData {
    layerId: LayerId
    layerCode: LayerCode
    legacyLayerIds: LayerId[]
}

const thunderforestApiKey: string = "9b990c27013343a99536213faee0983e"
const tracestrackApiKey: string = "684615014d1a572361803e062ccf609a"

const layerData: Map<L.Layer, LayerInstanceData> = new Map()

export const getLayerData = (layer: L.Layer): LayerInstanceData | undefined => layerData.get(layer)

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

// Base layers
const standardLayer = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: `${copyright} ♥ <a class="donate" href="https://supporting.openstreetmap.org" target="_blank" title="${donateTitle}">${donateText}</a>. ${terms}`,
})
layerData.set(standardLayer, {
    layerId: "standard" as LayerId,
    layerCode: "" as LayerCode, // Standard has no layer code - it's the default layer
    legacyLayerIds: ["mapnik"] as LayerId[],
})

const cyclosm = L.tileLayer("https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png", {
    maxZoom: 20,
    subdomains: "abc",
    attribution: `${copyright}. ${cyclosmCredit}. ${terms}`,
})
layerData.set(cyclosm, {
    layerId: "cyclosm" as LayerId,
    layerCode: "Y" as LayerCode,
    legacyLayerIds: [],
})

const cycleMap = L.tileLayer(`https://tile.thunderforest.com/cycle/{z}/{x}/{y}{r}.png?apikey=${thunderforestApiKey}`, {
    maxZoom: 21, // This layer supports up to 22
    attribution: `${copyright}. ${thunderforestCredit}. ${terms}`,
})
layerData.set(cycleMap, {
    layerId: "cyclemap" as LayerId,
    layerCode: "C" as LayerCode,
    legacyLayerIds: ["cycle map"] as LayerId[],
})

const transportMap = L.tileLayer(
    `https://tile.thunderforest.com/transport/{z}/{x}/{y}{r}.png?apikey=${thunderforestApiKey}`,
    {
        maxZoom: 21, // This layer supports up to 22
        attribution: `${copyright}. ${thunderforestCredit}. ${terms}`,
    },
)
layerData.set(transportMap, {
    layerId: "transportmap" as LayerId,
    layerCode: "T" as LayerCode,
    legacyLayerIds: [],
})

const tracestrackTopo = L.tileLayer(`https://tile.tracestrack.com/topo__/{z}/{x}/{y}.png?key=${tracestrackApiKey}`, {
    maxZoom: 19,
    attribution: `${copyright}. ${tracestrackCredit}. ${terms}`,
})
layerData.set(tracestrackTopo, {
    layerId: "tracestracktopo" as LayerId,
    layerCode: "P" as LayerCode,
    legacyLayerIds: [],
})

const hotosm = L.tileLayer("https://tile-{s}.openstreetmap.fr/hot/{z}/{x}/{y}.png", {
    maxZoom: 20,
    subdomains: "abc",
    attribution: `${copyright}. ${hotosmCredit}. ${terms}`,
})
layerData.set(hotosm, {
    layerId: "hot" as LayerId,
    layerCode: "H" as LayerCode,
    legacyLayerIds: [],
})

// Overlay layers
const aerial = L.tileLayer(
    "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {
        maxZoom: 21, // This layer supports up to 23
        attribution: aerialEsriCredit,
        opacity: getOverlayOpacity(),
        pane: "overlayPane",
        zIndex: 0,
    },
)
layerData.set(aerial, {
    layerId: "aerial" as LayerId,
    layerCode: "A" as LayerCode,
    legacyLayerIds: [],
})

const gps = L.tileLayer("https://gps.tile.openstreetmap.org/lines/{z}/{x}/{y}.png", {
    maxZoom: 21, // This layer has no zoom limits
    maxNativeZoom: 20,
    pane: "overlayPane",
})
layerData.set(gps, {
    layerId: "gps" as LayerId,
    layerCode: "G" as LayerCode,
    legacyLayerIds: [],
})

const dataLayer = L.featureGroup()
layerData.set(dataLayer, {
    layerId: "data" as LayerId,
    layerCode: "D" as LayerCode,
    legacyLayerIds: [],
})

const changesetLayer = L.featureGroup()
layerData.set(changesetLayer, {
    layerId: "changesets" as LayerId,
    layerCode: "" as LayerCode, // This layer is not possible to toggle manually
    legacyLayerIds: [],
})

const routingLayer = L.featureGroup()
layerData.set(routingLayer, {
    layerId: "routing" as LayerId,
    layerCode: "" as LayerCode, // This layer is not possible to toggle manually
    legacyLayerIds: [],
})

const searchLayer = L.featureGroup()
layerData.set(searchLayer, {
    layerId: "search" as LayerId,
    layerCode: "" as LayerCode, // This layer is not possible to toggle manually
    legacyLayerIds: [],
})

const noteLayer = L.featureGroup()
layerData.set(noteLayer, {
    layerId: "notes" as LayerId,
    layerCode: "N" as LayerCode,
    legacyLayerIds: [],
})

const focusLayer = L.featureGroup()
layerData.set(focusLayer, {
    layerId: "focus" as LayerId,
    layerCode: "" as LayerCode, // This layer is not possible to toggle manually
    legacyLayerIds: [],
})

const baseLayerIdMap: Map<LayerId, L.TileLayer> = new Map()
for (const layer of [standardLayer, cyclosm, cycleMap, transportMap, tracestrackTopo, hotosm]) {
    const data = getLayerData(layer)
    baseLayerIdMap.set(data.layerId, layer)
}

const overlayLayerIdMap: Map<LayerId, L.Layer> = new Map()
for (const layer of [gps, dataLayer, changesetLayer, routingLayer, searchLayer, noteLayer, focusLayer, aerial]) {
    const data = getLayerData(layer)
    overlayLayerIdMap.set(data.layerId, layer)
    for (const legacyLayerId of data.legacyLayerIds) {
        overlayLayerIdMap.set(legacyLayerId, layer)
    }
}

const layerCodeIdMap: Map<LayerCode, LayerId> = new Map()
for (const layer of [...baseLayerIdMap.values(), ...overlayLayerIdMap.values()]) {
    const data = getLayerData(layer)
    if (data.layerCode || data.layerId === "standard") layerCodeIdMap.set(data.layerCode, data.layerId)
}

/** Get base layer instance by id */
export const getBaseLayerById = (layerId: LayerId): L.TileLayer | undefined => baseLayerIdMap.get(layerId)

/** Get the default base layer instance */
export const getDefaultBaseLayer = (): L.TileLayer => getBaseLayerById(getLayerIdByCode("" as LayerCode))

/** Get overlay layer instance by id */
export const getOverlayLayerById = (layerId: LayerId): L.Layer | L.FeatureGroup | undefined =>
    overlayLayerIdMap.get(layerId)

/**
 * Get layer id by code
 * @example
 * getLayerIdByCode("")
 * // => "standard"
 */
export const getLayerIdByCode = (layerCode: LayerCode): LayerId | undefined => {
    if (layerCode.length > 1) {
        console.error("Invalid layer code", layerCode)
        layerCode = layerCode[0] as LayerCode
    }
    return layerCodeIdMap.get(layerCode)
}
