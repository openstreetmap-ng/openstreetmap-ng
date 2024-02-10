import i18next from "i18next"
import * as L from "leaflet"
import { thunderforestApiKey, tracestrackApiKey } from "../_api-keys.js"
import "../_types.js"

const copyrightText = i18next.t("javascripts.map.openstreetmap_contributors")
const copyright = `© <a href="https://www.openstreetmap.org/copyright" rel="license" target="_blank">${copyrightText}</a>`
const termsText = i18next.t("javascripts.map.website_and_api_terms")
const terms = `<a href="https://wiki.osmfoundation.org/wiki/Terms_of_Use" rel="terms-of-service" target="_blank">${termsText}</a>`

const donateTitle = i18next.t("layouts.make_a_donation.title")
const donateText = i18next.t("layouts.make_a_donation.text")

const standardLayer = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: `${copyright} ♥ <a class="donate" href="https://supporting.openstreetmap.org" target="_blank" title="${donateTitle}">${donateText}</a>. ${terms}`,
    layerCode: "", // Standard has no layer code - it's the default layer
    layerId: "standard",
    legacyLayerIds: ["mapnik"],
})

const osmFranceText = i18next.t("javascripts.map.osm_france")
const osmFranceLink = `<a href="https://openstreetmap.fr" target="_blank">${osmFranceText}</a>`

const cyclosmText = i18next.t("javascripts.map.cyclosm_name")
const cyclosmLink = `<a href="https://www.cyclosm.org" target="_blank">${cyclosmText}</a>`
const cyclosmCredit = i18next.t("javascripts.map.cyclosm_credit", {
    // biome-ignore lint/style/useNamingConvention:
    cyclosm_link: cyclosmLink,
    // biome-ignore lint/style/useNamingConvention:
    osm_france_link: osmFranceLink,
})

const cyclosm = L.tileLayer("https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png", {
    maxZoom: 20,
    subdomains: "abc",
    attribution: `${copyright}. ${cyclosmCredit}. ${terms}`,
    layerCode: "Y",
    layerId: "cyclosm",
})

const thunderforestText = i18next.t("javascripts.map.andy_allan")
const thunderforestLink = `<a href="https://www.thunderforest.com" target="_blank">${thunderforestText}</a>`
const thunderforestCredit = i18next.t("javascripts.map.thunderforest_credit", {
    // biome-ignore lint/style/useNamingConvention:
    thunderforest_link: thunderforestLink,
})

const cycleMap = L.tileLayer("https://tile.thunderforest.com/cycle/{z}/{x}/{y}{r}.png?apikey={apiKey}", {
    maxZoom: 21, // supports up to 22
    attribution: `${copyright}. ${thunderforestCredit}. ${terms}`,
    apiKey: thunderforestApiKey,
    layerCode: "C",
    layerId: "cyclemap",
    legacyLayerIds: ["cycle map"],
})

const transportMap = L.tileLayer("https://tile.thunderforest.com/transport/{z}/{x}/{y}{r}.png?apikey={apiKey}", {
    maxZoom: 21, // supports up to 22
    attribution: `${copyright}. ${thunderforestCredit}. ${terms}`,
    apiKey: thunderforestApiKey,
    layerCode: "T",
    layerId: "transportmap",
})

const tracestrackText = i18next.t("javascripts.map.tracestrack")
const tracestrackLink = `<a href="https://www.tracestrack.com" target="_blank">${tracestrackText}</a>`
const tracestrackCredit = i18next.t("javascripts.map.tracestrack_credit", {
    // biome-ignore lint/style/useNamingConvention:
    tracestrack_link: tracestrackLink,
})

const tracestrackTopo = L.tileLayer("https://tile.tracestrack.com/topo__/{z}/{x}/{y}.png?key={apiKey}", {
    maxZoom: 19,
    attribution: `${copyright}. ${tracestrackCredit}. ${terms}`,
    apiKey: tracestrackApiKey,
    layerCode: "P",
    layerId: "tracestracktopo",
})

const hotosmText = i18next.t("javascripts.map.hotosm_name")
const hotosmLink = `<a href="https://www.hotosm.org" target="_blank">${hotosmText}</a>`
const hotosmCredit = i18next.t("javascripts.map.hotosm_credit", {
    // biome-ignore lint/style/useNamingConvention:
    hotosm_link: hotosmLink,
    // biome-ignore lint/style/useNamingConvention:
    osm_france_link: osmFranceLink,
})

const hotosm = L.tileLayer("https://tile.openstreetmap.fr/hot/{z}/{x}/{y}.png", {
    maxZoom: 20,
    attribution: `${copyright}. ${hotosmCredit}. ${terms}`,
    layerCode: "H",
    layerId: "hot",
})

const gps = L.tileLayer("https://gps.tile.openstreetmap.org/lines/{z}/{x}/{y}.png", {
    // This layer has no zoom limits
    maxZoom: 21,
    maxNativeZoom: 20,
    layerCode: "G",
    layerId: "gps",
    pane: "overlayPane",
})

const noteLayer = L.featureGroup(undefined, {
    layerCode: "N",
    layerId: "notes",
})

const dataLayer = L.featureGroup(undefined, {
    layerCode: "D",
    layerId: "data",
})

const focusLayer = L.featureGroup(undefined, {
    inaccessible: true,
    layerCode: "", // This layer is not possible to toggle manually
    layerId: "focus",
})

const baseLayerIdMap = [standardLayer, cyclosm, cycleMap, transportMap, tracestrackTopo, hotosm].reduce(
    (map, layer) => map.set(layer.options.layerId, layer),
    new Map(),
)

/**
 * Get base layer instance by id
 * @param {string} layerId Layer id
 * @returns {L.TileLayer} Layer instance
 */
export const getBaseLayerById = (layerId) => baseLayerIdMap.get(layerId)

const overlayLayerIdMap = [gps, noteLayer, dataLayer, focusLayer].reduce((map, layer) => {
    const options = layer.options
    map.set(options.layerId, layer)
    if (options.legacyLayerIds) {
        for (const legacyLayerId of options.legacyLayerIds) {
            map.set(legacyLayerId, layer)
        }
    }
    return map
}, new Map())

/**
 * Get overlay layer instance by id
 * @param {string} layerId Layer id
 * @returns {L.Layer|L.FeatureGroup} Layer instance
 */
export const getOverlayLayerById = (layerId) => overlayLayerIdMap.get(layerId)

const layerCodeIdMap = [...baseLayerIdMap.values(), ...overlayLayerIdMap.values()].reduce((map, layer) => {
    const options = layer.options
    return options.inaccessible ? map : map.set(options.layerCode, options.layerId)
}, new Map())

/**
 * Get layer id by code
 * @param {string} layerCode Layer code
 * @returns {string} Layer id
 * @example
 * getLayerIdByCode("")
 * // => "standard"
 */
export const getLayerIdByCode = (layerCode) => {
    if (layerCode.length > 1) {
        console.error("Invalid layer code", layerCode)
        return getLayerIdByCode("")
    }

    return layerCodeIdMap.get(layerCode)
}
