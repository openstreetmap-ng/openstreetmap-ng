import * as L from "leaflet"
import "../_types.js"
import { getMarkerIcon } from "./_utils.js"

const areaTagsSet = new Set([
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
])

const areaTagsPrefixes = ["area:"]

/**
 * Check if the given way is considered an area
 * @param {OSMWay} way Way
 * @returns {boolean} True if the way is an area
 */
const isWayArea = (way) => {
    if (way.members.length <= 2) return false

    const isClosedWay = way.members[0].id === way.members[way.members.length - 1].id
    if (!isClosedWay) return false

    for (const tagKey of way.tags.keys()) {
        // Check exact matches
        if (areaTagsSet.has(tagKey)) return true

        // Check prefix matches
        for (const prefix of areaTagsPrefixes) {
            if (tagKey.startsWith(prefix)) return true
        }
    }

    return false
}

/**
 * Add objects to the feature group layer
 * @param {L.LayerGroup} layerGroup Layer group
 * @param {OSMObject[]} objects Array of objects
 * @param {object} styles Styles
 * @param {object} styles.changeset Changeset style
 * @param {object} styles.element Element style
 * @param {object} styles.noteHalo Note halo style
 * @returns {L.Layer[]} Array of added layers
 */
export const renderObjects = (layerGroup, objects, styles) => {
    const layers = []
    const markers = []

    /**
     * @param {OSMChangeset} changeset
     */
    const processChangeset = (changeset) => {
        const layer = L.rectangle(changeset.bounds ?? [0, 0, 0, 0], styles.changeset)
        layer.object = changeset
        layers.push(layer)
    }

    /**
     * @param {OSMNote} note
     */
    const processNote = (note) => {
        const latLng = L.latLng(note.lat, note.lon)
        const interactive = note.interactive !== undefined ? Boolean(note.interactive) : true
        const draggable = note.draggable !== undefined ? Boolean(note.draggable) : false
        const layer = L.circleMarker(latLng, styles.noteHalo)
        const marker = L.marker(latLng, {
            icon: getMarkerIcon(note.icon, false),
            keyboard: interactive,
            interactive: interactive,
            draggable: draggable,
            autoPan: draggable,
        })
        layer.object = note
        layer.marker = marker
        layers.push(layer)
        markers.push(marker)
    }

    /**
     * @param {OSMNode} node
     */
    const processNode = (node) => {
        const layer = L.circleMarker(L.latLng(node.lat, node.lon), styles.element)
        layer.object = node
        layers.push(layer)
    }

    /**
     * @param {OSMWay} way
     */
    const processWay = (way) => {
        const members = way.members
        const latLngs = members.map((node) => L.latLng(node.lat, node.lon))
        let layer

        if (isWayArea(way)) {
            // is "area"
            latLngs.pop() // remove last == first
            layer = L.polygon(latLngs, styles.element)
        } else {
            // is way
            layer = L.polyline(latLngs, styles.element)
        }

        layer.object = way
        layers.push(layer)

        for (const member of members) {
            const interesting = member.interesting !== undefined ? member.interesting : true
            if (interesting) processNode(member)
        }
    }

    /**
     * @param {OSMRelation} relation
     */
    const processRelation = (relation) => {
        for (const member of relation.members) {
            if (member.type === "node") {
                const interesting = member.interesting !== undefined ? member.interesting : true
                if (interesting) processNode(member)
            } else if (member.type === "way") {
                processWay(member)
            }
        }
    }

    const processMap = {
        changeset: processChangeset,
        note: processNote,
        node: processNode,
        way: processWay,
        relation: processRelation,
    }

    for (const object of objects) {
        const objectType = object.type
        const fn = processMap[objectType]
        if (fn) fn(object)
        else console.error(`Unsupported feature type: ${objectType}`)
    }

    // Render icons on top of the feature layers
    if (layers.length) layerGroup.addLayer(L.layerGroup(layers))
    if (markers.length) layerGroup.addLayer(L.layerGroup(markers))

    return layers
}
