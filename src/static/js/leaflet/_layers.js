import * as L from "leaflet"

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

const DataLayer = L.FeatureGroup.extend({
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

    addData: function (featuresOrXml) {
        let features

        // Parse XML if necessary
        if (Array.isArray(featuresOrXml)) features = featuresOrXml
        else features = this.buildFeatures(featuresOrXml)

        for (const feature of features) {
            let layer

            switch (feature.type) {
                case "changeset":
                    layer = L.rectangle(feature.latLngBounds, this.options.styles.changeset)
                    break
                case "node":
                    layer = L.circleMarker(feature.latLng, this.options.styles.object)
                    break
                default: {
                    const latLngs = feature.nodes.map((node) => node.latLng)
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
            }

            this.addLayer(layer)
            layer.feature = feature
        }
    },

    buildFeatures: function (xml) {
        const changesets = getChangesets(xml)
        const nodes = getNodes(xml)
        const ways = getWays(xml, nodes)
        const relations = getRelations(xml, nodes, ways)

        const interestingNodes = Object.values(nodes).filter((node) => this.isInterestingNode(node, ways, relations))
        const features = [...changesets, ...ways, ...interestingNodes]
        return features
    },

    isWayArea: function (way) {
        if (way.nodes.length <= 2) return false

        const isClosedWay = way.nodes[0] === way.nodes[way.nodes.length - 1]
        if (!isClosedWay) return false

        const hasAreaTag = Object.keys(way.tags).some((key) => this.options.areaTags.includes(key))
        return hasAreaTag
    },

    isInterestingNode: (node, ways, relations) => {
        const usedInWay = ways.some((way) => way.nodes.includes(node))
        if (!usedInWay) return true

        const usedInRelation = relations.some((relation) => relation.members.includes(node))
        if (!usedInRelation) return true

        const hasTags = Object.keys(node.tags).length > 0
        return hasTags
    },
})

const getChangesets = (xml) => {
    const nodes = Array.from(xml.getElementsByTagName("changeset"))
    return nodes.map((node) => ({
        id: node.getAttribute("id"),
        type: "changeset",
        latLngBounds: L.latLngBounds(
            [node.getAttribute("min_lat"), node.getAttribute("min_lon")],
            [node.getAttribute("max_lat"), node.getAttribute("max_lon")],
        ),
        tags: getTags(node),
    }))
}

const getNodes = (xml) => {
    const nodes = Array.from(xml.getElementsByTagName("node"))
    return nodes.reduce((result, node) => {
        const id = node.getAttribute("id")
        result[id] = {
            id: id,
            type: "node",
            latLng: L.latLng(node.getAttribute("lat"), node.getAttribute("lon")),
            tags: getTags(node),
        }
        return result
    }, {})
}

const getWays = (xml, nodes) => {
    const ways = Array.from(xml.getElementsByTagName("way"))
    return ways.map((way) => {
        const nodesIds = Array.from(way.getElementsByTagName("nd"))
        const nodesArray = nodesIds.map((nd) => nodes[nd.getAttribute("ref")])

        return {
            id: way.getAttribute("id"),
            type: "way",
            nodes: nodesArray,
            tags: getTags(way),
        }
    })
}

const getRelations = (xml, nodes, ways) => {
    const rels = Array.from(xml.getElementsByTagName("relation"))
    return rels.map((rel) => {
        const members = Array.from(rel.getElementsByTagName("member"))

        return {
            id: rel.getAttribute("id"),
            type: "relation",
            members: members.map((member) => {
                const memberType = member.getAttribute("type")
                if (memberType === "node") return nodes[member.getAttribute("ref")]

                // member ways and relations are not currently used, skip them
                return null
            }),
            tags: getTags(rel),
        }
    })
}

const getTags = (xml) => {
    const tags = Array.from(xml.getElementsByTagName("tag"))
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

export const getBaseLayerById = (layerId) => BASE_LAYER_ID_MAP[layerId]

const OVERLAY_LAYER_ID_MAP = [GPS, NoteLayer, DataLayer].reduce((result, layer) => {
    result[layer.options.layerId] = new layer()
    return result
}, {})

export const getOverlayLayerById = (layerId) => OVERLAY_LAYER_ID_MAP[layerId]

const CODE_ID_MAP = [...Object.values(BASE_LAYER_ID_MAP), ...Object.values(OVERLAY_LAYER_ID_MAP)].reduce(
    (result, layer) => {
        // Default layer has no code
        result[layer.options.layerCode ?? ""] = layer.options.layerId
        return result
    },
    {},
)

// Decodes layer code to layer id
// To get default layer id by code use: getLayerIdByCode("")
export const getLayerIdByCode = (layerCode) => CODE_ID_MAP[layerCode]
