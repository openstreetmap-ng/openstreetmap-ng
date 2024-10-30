import * as L from "leaflet"

import type { OSMChangeset, OSMNode, OSMNote, OSMObject, OSMWay } from "../_types"
import { getMarkerIcon } from "./_utils"

export interface RenderStyles {
    changeset?: Partial<L.PolylineOptions>
    element?: Partial<L.CircleMarkerOptions>
    note?: Partial<L.MarkerOptions>
    noteHalo?: Partial<L.CircleMarkerOptions>
}

interface RenderOptions {
    /** Whether to render areas */
    renderAreas: boolean
}

/** Add objects to the feature group layer */
export const renderObjects = (
    layerGroup: L.LayerGroup,
    objects: OSMObject[],
    styles: RenderStyles,
    options?: Partial<RenderOptions>,
): L.Layer[] => {
    const layers: L.Layer[] = []
    const markers: L.Marker[] = []

    const processChangeset = (changeset: OSMChangeset): void => {
        for (const [minLon, minLat, maxLon, maxLat] of changeset.bounds ?? []) {
            const latLngBounds = L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
            const layer = L.rectangle(latLngBounds, styles.changeset)
            // @ts-ignore
            layer.object = changeset
            layers.push(layer)
        }
    }

    const processNote = (note: OSMNote): void => {
        const interactive = note.interactive !== undefined ? Boolean(note.interactive) : true
        const draggable = note.draggable !== undefined ? Boolean(note.draggable) : false
        const latLng = L.latLng(note.geom)
        const layer = L.circleMarker(latLng, styles.noteHalo as L.CircleMarkerOptions)
        const marker = L.marker(latLng, {
            ...styles.note,
            icon: getMarkerIcon(note.icon, false),
            keyboard: interactive,
            interactive: interactive,
            draggable: draggable,
            autoPan: draggable,
        })
        // @ts-ignore
        layer.object = note
        // @ts-ignore
        layer.marker = marker
        layers.push(layer)
        markers.push(marker)
    }

    const processNode = (node: OSMNode): void => {
        const layer = L.circleMarker(node.geom, styles.element as L.CircleMarkerOptions)
        // @ts-ignore
        layer.object = node
        layers.push(layer)
    }

    const processWay = (way: OSMWay): void => {
        let geom = way.geom
        let layer: L.Layer
        if ((options?.renderAreas ?? true) && way.area) {
            geom = geom.slice(0, -1) // remove last == first
            layer = L.polygon(geom, styles.element)
        } else {
            layer = L.polyline(geom, styles.element)
        }
        // @ts-ignore
        layer.object = way
        layers.push(layer)
    }

    const processFnMap = {
        changeset: processChangeset,
        note: processNote,
        node: processNode,
        way: processWay,
    }

    for (const object of objects) {
        // @ts-ignore
        const fn = processFnMap[object.type]
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
