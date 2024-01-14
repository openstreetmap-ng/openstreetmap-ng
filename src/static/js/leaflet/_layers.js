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

const Mapnik = defaultLayer.extend({
    options: {
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        maxZoom: 19,
        attribution: `${copyright} ♥ <a class="donate" href="https://supporting.openstreetmap.org" target="_blank">Make a Donation</a>. ${terms}`,
        // Mapnik has no layer code, it's the default layer
        // layerCode: "M",
        layerId: "mapnik",
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
        style: {
            weight: 2.5,
            radius: 20,
            fillOpacity: 0.5,
            color: "#FF6200",
        },
    },
})

export const DataLayer = L.FeatureGroup.extend({
    options: {
        layerCode: "D",
        layerId: "data",
        areaTags: [
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
        ],
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
                    layer = L.circleMarker(latLng, this.options.styles.object)
                    layer.marker = L.marker(latLng, { icon: getMarkerIcon(feature.icon, false) })
                    markers.push(layer.marker)
                    break
                }
                case "node":
                    layer = L.circleMarker(L.latLng(feature.lat, feature.lon), this.options.styles.object)
                    break
                case "way": {
                    const latLngs = feature.nodes.map((node) => L.latLng(node.lat, node.lon))
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
                    throw new Error(`Unsupported feature type: ${feature.type}`)
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
     * Parse features from the given XML string
     * @param {string} xml XML string
     * @returns {OSMObject[]} Array of features
     */
    parseFeaturesFromXML: function (xml) {
        const changesets = getChangesets(xml)
        const nodes = getNodesMap(xml)
        const ways = getWays(xml, nodes)
        const relations = getRelations(xml, nodes, ways)

        const interestingNodes = Object.values(nodes).filter((node) => this.isInterestingNode(node, ways, relations))
        const features = [...changesets, ...ways, ...interestingNodes]
        return features
    },

    /**
     * Check if the given way is considered an area
     * @param {OSMWay} way Way
     * @returns {boolean} True if the way is an area
     */
    isWayArea: function (way) {
        if (way.nodes.length <= 2) return false

        const isClosedWay = way.nodes[0].id === way.nodes[way.nodes.length - 1].id
        if (!isClosedWay) return false

        const hasAreaTag = Object.keys(way.tags).some((key) => this.options.areaTags.includes(key))
        return hasAreaTag
    },

    /**
     * Check if the given node is interesting to display
     * @param {OSMNode} node Node
     * @param {OSMWay[]} ways Ways
     * @param {OSMRelation[]} relations Relations
     * @returns {boolean} True if the node is interesting
     */
    isInterestingNode: (node, ways, relations) => {
        // TODO: this could be optimized with set
        const usedInWay = ways.some((way) => way.nodes.includes(node))
        if (!usedInWay) return true

        const usedInRelation = relations.some((relation) => relation.members.includes(node))
        if (!usedInRelation) return true

        const hasTags = Object.keys(node.tags).length > 0
        return hasTags
    },
})

/**
 * Parse changesets from the given XML string
 * @param {string} xml XML string
 * @returns {OSMChangeset[]} Array of changesets
 */
const getChangesets = (xml) => {
    const changesets = Array.from(xml.getElementsByTagName("changeset"))
    return changesets.map((cs) => ({
        type: "changeset",
        id: parseInt(cs.getAttribute("id"), 10),
        tags: getTagsMap(cs),
        // Empty changesets have no bounds
        bounds: cs.hasAttribute("min_lat")
            ? [
                  parseFloat(cs.getAttribute("min_lat")),
                  parseFloat(cs.getAttribute("min_lon")),
                  parseFloat(cs.getAttribute("max_lat")),
                  parseFloat(cs.getAttribute("max_lon")),
              ]
            : null,
    }))
}

/**
 * Parse nodes map from the given XML string
 * @param {string} xml XML string
 * @returns {object} Nodes map
 */
const getNodesMap = (xml) => {
    const nodes = Array.from(xml.getElementsByTagName("node"))
    return nodes.reduce((result, node) => {
        const id = parseInt(node.getAttribute("id"), 10)
        result[id] = {
            type: "node",
            id: id,
            version: parseInt(node.getAttribute("version"), 10),
            tags: getTagsMap(node),
            lon: parseFloat(node.getAttribute("lon")),
            lat: parseFloat(node.getAttribute("lat")),
        }
        return result
    }, {})
}

/**
 * Parse ways from the given XML string
 * @param {string} xml XML string
 * @param {object} nodesMap Nodes map
 * @returns {OSMWay[]} Array of ways
 */
const getWays = (xml, nodesMap) => {
    const ways = Array.from(xml.getElementsByTagName("way"))
    return ways.map((way) => {
        const nodesMembers = Array.from(way.getElementsByTagName("nd"))
        const nodesArray = nodesMembers.map((nd) => nodesMap[nd.getAttribute("ref")])
        return {
            type: "way",
            id: way.getAttribute("id"),
            version: parseInt(way.getAttribute("version"), 10),
            tags: getTagsMap(way),
            nodes: nodesArray,
        }
    })
}

/**
 * Parse relations from the given XML string
 * @param {string} xml XML string
 * @param {object} nodesMap Nodes map
 * @returns {OSMRelation[]} Array of relations
 */
const getRelations = (xml, nodesMap) => {
    const rels = Array.from(xml.getElementsByTagName("relation"))
    return rels.map((rel) => {
        const members = Array.from(rel.getElementsByTagName("member"))
        return {
            id: rel.getAttribute("id"),
            type: "relation",
            members: members.map((member) => {
                // Member ways and relations are not currently used, ignore them
                const memberType = member.getAttribute("type")
                return memberType === "node" ? nodesMap[member.getAttribute("ref")] : null
            }),
            tags: getTagsMap(rel),
        }
    })
}

/**
 * Parse tags from the given XML element
 * @param {Element} element XML element
 * @returns {object} Tags map
 */
const getTagsMap = (element) => {
    const tags = Array.from(element.getElementsByTagName("tag"))
    return tags.reduce((result, tag) => {
        result[tag.getAttribute("k")] = tag.getAttribute("v")
        return result
    }, {})
}

const BASE_LAYER_ID_MAP = [Mapnik, CyclOSM, CycleMap, TransportMap, TracestrackTopo, OPNVKarte, HOT].reduce(
    (result, layer) => {
        result[layer.options.layerId] = new layer()
        return result
    },
    {},
)

/**
 * Get base layer instance by id
 * @param {string} layerId Layer id
 * @returns {L.TileLayer} Layer instance
 */
export const getBaseLayerById = (layerId) => BASE_LAYER_ID_MAP[layerId]

const OVERLAY_LAYER_ID_MAP = [GPS, NoteLayer, DataLayer].reduce((result, layer) => {
    result[layer.options.layerId] = new layer()
    return result
}, {})

/**
 * Get overlay layer instance by id
 * @param {string} layerId Layer id
 * @returns {L.Layer} Layer instance
 */
export const getOverlayLayerById = (layerId) => OVERLAY_LAYER_ID_MAP[layerId]

const CODE_ID_MAP = [...Object.values(BASE_LAYER_ID_MAP), ...Object.values(OVERLAY_LAYER_ID_MAP)].reduce(
    (result, layer) => {
        // Default layer has no code
        result[layer.options.layerCode ?? ""] = layer.options.layerId
        return result
    },
    {},
)

/**
 * Get layer id by code
 * @param {string} layerCode Layer code
 * @returns {string} Layer id
 * @example
 * getLayerIdByCode("")
 * // => "mapnik"
 */
export const getLayerIdByCode = (layerCode) => {
    if (layerCode.length > 1) throw new Error(`Invalid layer code: ${layerCode}`)
    return CODE_ID_MAP[layerCode]
}
