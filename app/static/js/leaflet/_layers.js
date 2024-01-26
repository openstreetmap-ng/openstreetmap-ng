import * as L from "leaflet"
import "../_types.js"
import { getMarkerIcon } from "./_utils.js"

// There is no point to keep these secret, they are a part of the frontend code
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

export const DataLayer = L.FeatureGroup.extend({
    options: {
        layerCode: "D",
        layerId: "data",
        areaTagsSet: new Set([
            "area",
            "building",
            "leisure",
            "tourism",
            "ruins",
            "historic",
            "landuse",
            "military",
            "natural",
            "sport",
        ]),
        styles: {
            object: {
                color: "#FF6200",
                weight: 4,
                opacity: 1,
                fillOpacity: 0.5,
            },
            changeset: {
                weight: 4,
                color: "#FF9500",
                opacity: 1,
                fillOpacity: 0,
                keyboard: false,
                interactive: false,
            },
            noteHalo: {
                weight: 2.5,
                radius: 20,
                fillOpacity: 0.5,
                color: "#FF6200",
                keyboard: false,
                interactive: false,
            },
        },
    },

    /**
     * Add data to the layer
     * @param {OSMObject[]} features Array of features
     * @returns {L.Layer[]} Array of added layers
     */
    addData: function (features) {
        const featureLayers = []
        const markers = []

        for (const feature of features) {
            let layer

            switch (feature.type) {
                case "changeset":
                    layer = L.rectangle(feature.bounds ?? [0, 0, 0, 0], this.options.styles.changeset)
                    break
                case "note": {
                    const latLng = L.latLng(feature.lat, feature.lon)
                    const interactive = feature.interactive !== undefined ? Boolean(feature.interactive) : true
                    const draggable = Boolean(feature.draggable)
                    layer = L.circleMarker(latLng, this.options.styles.noteHalo)
                    layer.marker = L.marker(latLng, {
                        icon: getMarkerIcon(feature.icon, false),
                        keyboard: interactive,
                        interactive: interactive,
                        draggable: draggable,
                        autoPan: draggable,
                    })
                    markers.push(layer.marker)
                    break
                }
                case "node":
                    layer = L.circleMarker(L.latLng(feature.lat, feature.lon), this.options.styles.object)
                    break
                case "way": {
                    const latLngs = feature.members.map((node) => L.latLng(node.lat, node.lon))
                    if (this.isWayArea(feature)) {
                        // is "area"
                        latLngs.pop() // remove last == first
                        layer = L.polygon(latLngs, this.options.styles.object)
                    } else {
                        // is way
                        layer = L.polyline(latLngs, this.options.styles.object)
                    }
                    break
                }
                default:
                    console.error(`Unsupported feature type: ${feature.type}`)
                    continue
            }

            layer.feature = feature
            this.addLayer(layer)
            featureLayers.push(layer)
        }

        // Render icons on top of the feature layers
        for (const marker of markers) {
            this.addLayer(marker)
        }

        return featureLayers
    },

    /**
     * Check if the given way is considered an area
     * @param {OSMWay} way Way
     * @returns {boolean} True if the way is an area
     */
    isWayArea: function (way) {
        if (way.members.length <= 2) return false

        const isClosedWay = way.members[0].id === way.members[way.members.length - 1].id
        if (!isClosedWay) return false

        const areaTagsSet = this.options.areaTagsSet
        for (const tagKey of way.tags.keys()) {
            if (areaTagsSet.has(tagKey)) return true
        }

        return false
    },
})

/**
 * Check if the given node is interesting to display
 * @param {OSMNode} node Node
 * @param {Set<string>} membersSet Set of all members in "n123" format
 * @returns {boolean} True if the node is interesting
 */
export const isInterestingNode = (node, membersSet) => {
    if (node.type !== "node") {
        console.error(`Invalid node type: ${node.type}`)
        return true
    }

    const isMember = membersSet.has(`n${node.id}`)
    if (!isMember) return true

    const hasTags = node.tags.size > 0
    return hasTags
}

const BASE_LAYER_ID_MAP = [StandardLayer, CyclOSM, CycleMap, TransportMap, TracestrackTopo, OPNVKarte, HOT].reduce(
    (map, layer) => map.set(layer.options.layerId, new layer()),
    new Map(),
)

/**
 * Get base layer instance by id
 * @param {string} layerId Layer id
 * @returns {L.TileLayer} Layer instance
 */
export const getBaseLayerById = (layerId) => BASE_LAYER_ID_MAP.get(layerId)

const OVERLAY_LAYER_ID_MAP = [GPS, NoteLayer, DataLayer].reduce((map, layer) => {
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
 * @returns {L.Layer} Layer instance
 */
export const getOverlayLayerById = (layerId) => OVERLAY_LAYER_ID_MAP.get(layerId)

const CODE_ID_MAP = [...BASE_LAYER_ID_MAP.values(), ...OVERLAY_LAYER_ID_MAP.values()].reduce(
    (map, layer) => map.set(layer.options.layerCode, layer.options.layerId),
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

    return CODE_ID_MAP.get(layerCode)
}
