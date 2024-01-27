import * as L from "leaflet"
import "../_types.js"

// There is no point to keep these secret, they are a part of the frontend code
// It's on the tile server to secure against abuse
const thunderforestApiKey = "6e5478c8a4f54c779f85573c0e399391"
const tracestrackApiKey = "383118983d4a867dd2d367451720d724"

const copyright = '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap contributors</a>'
const terms = '<a href="https://wiki.osmfoundation.org/wiki/Terms_of_Use" target="_blank">Website and API terms</a>'

const defaultLayer = L.TileLayer.extend({
    options: {},
    initialize: (options) => {
        const mergedOptions = L.Util.setOptions(this, options)
        L.TileLayer.prototype.initialize.call(this, mergedOptions.url)
    },
})

// TODO: translations
const StandardLayer = defaultLayer.extend({
    options: {
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        maxZoom: 19,
        attribution: `${copyright} ♥ <a class="donate" href="https://supporting.openstreetmap.org" target="_blank">Make a Donation</a>. ${terms}`,
        layerCode: "", // Standard has no layer code - it's the default layer
        layerId: "standard",
        legacyLayerIds: ["mapnik"],
    },
})

const CyclOSM = defaultLayer.extend({
    options: {
        url: "https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png",
        maxZoom: 20,
        subdomains: "abc",
        attribution: `${copyright}. Tiles style by <a href="https://www.cyclosm.org" target="_blank">CyclOSM</a> hosted by <a href="https://openstreetmap.fr" target="_blank">OpenStreetMap France</a>. ${terms}`,
        layerCode: "Y",
        layerId: "cyclosm",
    },
})

const CycleMap = defaultLayer.extend({
    options: {
        url: "https://tile.thunderforest.com/cycle/{z}/{x}/{y}{r}.png?apikey={apiKey}",
        maxZoom: 21, // supports up to 22
        attribution: `${copyright}. Tiles courtesy of <a href="https://www.thunderforest.com" target="_blank">Andy Allan</a>. ${terms}`,
        apiKey: thunderforestApiKey,
        layerCode: "C",
        layerId: "cyclemap",
        legacyLayerIds: ["cycle map"],
    },
})

const TransportMap = defaultLayer.extend({
    options: {
        url: "https://tile.thunderforest.com/transport/{z}/{x}/{y}{r}.png?apikey={apiKey}",
        maxZoom: 21, // supports up to 22
        attribution: `${copyright}. Tiles courtesy of <a href="https://www.thunderforest.com" target="_blank">Andy Allan</a>. ${terms}`,
        apiKey: thunderforestApiKey,
        layerCode: "T",
        layerId: "transportmap",
    },
})

const TracestrackTopo = defaultLayer.extend({
    options: {
        url: "https://tile.tracestrack.com/topo__/{z}/{x}/{y}.png?key={apiKey}",
        maxZoom: 19,
        attribution: `${copyright}. Tiles courtesy of <a href="https://www.tracestrack.com" target="_blank">Tracestrack</a>. ${terms}`,
        apiKey: tracestrackApiKey,
        layerCode: "P",
        layerId: "tracestracktopo",
    },
})

const OPNVKarte = defaultLayer.extend({
    options: {
        url: "https://tileserver.memomaps.de/tilegen/{z}/{x}/{y}.png",
        maxZoom: 17,
        attribution: `${copyright}. Tiles courtesy of <a href="https://memomaps.de" target="_blank">MeMoMaps</a>. ${terms}`,
        layerCode: "O",
        layerId: "opnvkarte",
    },
})

const HOT = defaultLayer.extend({
    options: {
        url: "https://tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        maxZoom: 20,
        attribution: `${copyright}. Tiles style by <a href="https://www.hotosm.org" target="_blank">Humanitarian OpenStreetMap Team</a> hosted by <a href="https://openstreetmap.fr" target="_blank">OpenStreetMap France</a>. ${terms}`,
        layerCode: "H",
        layerId: "hot",
    },
})

const GPS = defaultLayer.extend({
    options: {
        // This layer has no zoom limits
        url: "https://gps.tile.openstreetmap.org/lines/{z}/{x}/{y}.png",
        maxZoom: 21,
        maxNativeZoom: 20,
        layerCode: "G",
        layerId: "gps",
        pane: "overlayPane",
    },
})

const NoteLayer = L.FeatureGroup.extend({
    options: {
        layerCode: "N",
        layerId: "notes",
    },
})

const DataLayer = L.FeatureGroup.extend({
    options: {
        layerCode: "D",
        layerId: "data",
    },
})

const FocusLayer = L.FeatureGroup.extend({
    options: {
        inaccessible: true,
        layerCode: "", // This layer is not possible to toggle manually
        layerId: "focus",
    },
})

const baseLayerIdMap = [StandardLayer, CyclOSM, CycleMap, TransportMap, TracestrackTopo, OPNVKarte, HOT].reduce(
    (map, layer) => map.set(layer.options.layerId, new layer()),
    new Map(),
)

/**
 * Get base layer instance by id
 * @param {string} layerId Layer id
 * @returns {L.TileLayer} Layer instance
 */
export const getBaseLayerById = (layerId) => baseLayerIdMap.get(layerId)

const overlayLayerIdMap = [GPS, NoteLayer, DataLayer, FocusLayer].reduce((map, layer) => {
    const instance = new layer()
    map.set(layer.options.layerId, instance)
    if (layer.options.legacyLayerIds) {
        for (const legacyLayerId of layer.options.legacyLayerIds) {
            map.set(legacyLayerId, instance)
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

const layerCodeIdMap = [...baseLayerIdMap.values(), ...overlayLayerIdMap.values()].reduce(
    (map, layer) => (layer.options.inaccessible ? map : map.set(layer.options.layerCode, layer.options.layerId)),
    new Map(),
)

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
        console.error(`Invalid layer code: ${layerCode}`)
        return getLayerIdByCode("")
    }

    return layerCodeIdMap.get(layerCode)
}
