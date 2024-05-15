import * as L from "leaflet"
import "../_types.js"
import { getMarkerIcon } from "./_utils.js"


/**
 * Add objects to the feature group layer
 * @param {L.LayerGroup} layerGroup Layer group
 * @param {OSMObject[]} objects Array of objects
 * @param {object} styles Styles
 * @param {object} styles.changeset Changeset style
 * @param {object} styles.element Element style
 * @param {object} styles.noteHalo Note halo style
 * @param {boolean} renderAreas Whether to render areas
 * @returns {L.Layer[]} Array of added layers
 */
export const renderObjects = (layerGroup, objects, styles, renderAreas = true) => {
    const layers = []
    const markers = []

    /**
     * @param {OSMChangeset} changeset
     */
    const processChangeset = (changeset) => {
        const [minLon, minLat, maxLon, maxLat] = changeset.bounds ?? [0, 0, 0, 0]
        const latLngBounds = L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
        const layer = L.rectangle(latLngBounds, styles.changeset)
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
        const [lon, lat] = node.geom
        const layer = L.circleMarker(L.latLng(lat, lon), styles.element)
        layer.object = node
        layers.push(layer)
    }

    /**
     * @param {OSMWay} way
     */
    const processWay = (way) => {
        const latLngs = []
        const geom = way.geom

        for (let i = 0; i < geom.length; i += 2) {
            const lon = geom[i]
            const lat = geom[i + 1]
            latLngs.push(L.latLng(lat, lon))
        }

        let layer
        if (renderAreas && way.area) {
            latLngs.pop() // remove last == first
            layer = L.polygon(latLngs, styles.element)
        } else {
            layer = L.polyline(latLngs, styles.element)
        }

        layer.object = way
        layers.push(layer)
    }

    const processMap = {
        changeset: processChangeset,
        note: processNote,
        node: processNode,
        way: processWay,
    }

    for (const object of objects) {
        const fn = processMap[object.type]
        if (fn) fn(object)
        else console.error("Unsupported feature type", object)
    }

    // Render icons on top of the feature layers
    if (layers.length) {
        console.debug("Render", layers.length, "objects")
        layerGroup.addLayer(L.layerGroup(layers))
    }
    if (markers.length) {
        console.debug("Render", markers.length, "markers")
        layerGroup.addLayer(L.layerGroup(markers))
    }

    return layers
}
