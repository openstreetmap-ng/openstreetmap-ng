import * as L from "leaflet"
import "../_types.js"
import { getOverlayLayerById } from "./_layers.js"
import { renderObjects } from "./_object-render.js"

export const focusStyles = {
    changeset: {
        color: "#FF9500",
        weight: 2,
        opacity: 1,
        fillColor: "#FFFFAF",
        fillOpacity: 0,
        interactive: true,
    },
    element: {
        color: "#FF6200",
        weight: 4,
        opacity: 1,
        fillOpacity: 0.5,
        interactive: false,
    },
    noteHalo: {
        radius: 20,
        color: "#FF6200",
        weight: 2.5,
        opacity: 1,
        fillOpacity: 0.5,
        interactive: false,
    },
}

/**
 * Focus an object on the map and return its layer.
 * To unfocus, pass null as the object.
 * @param {L.Map} map Leaflet map
 * @param {OSMObject|null} object Object to focus
 * @returns {L.Layer[]} The layers of the focused object
 */
export const focusMapObject = (map, object) => {
    if (object) {
        return focusManyMapObjects(map, [object])
    }

    focusManyMapObjects(map, [])
    return []
}

/**
 * Focus many objects on the map and return their layers.
 * To unfocus, pass an empty array as the objects.
 * @param {L.Map} map Leaflet map
 * @param {OSMObject[]} objects Objects to focus
 * @returns {L.Layer[]} The layers of the focused objects
 */
export const focusManyMapObjects = (map, objects) => {
    const layer = getOverlayLayerById("focus")

    // Always clear the focus layer
    layer.clearLayers()

    // If there are no objects to focus, remove the focus layer
    if (!objects.length) {
        if (map.hasLayer(layer)) {
            map.removeLayer(layer)

            // Trigger the overlayremove event
            // https://leafletjs.com/reference.html#map-overlayremove
            // https://leafletjs.com/reference.html#layerscontrolevent
            map.fire("overlayremove", { layer: layer, name: layer.options.layerId })
        }

        return []
    }

    // TODO: z-index
    // Create the focus layer if it doesn't exist
    if (!map.hasLayer(layer)) {
        map.addLayer(layer)

        // Trigger the overlayadd event
        // https://leafletjs.com/reference.html#map-overlayadd
        // https://leafletjs.com/reference.html#layerscontrolevent
        map.fire("overlayadd", { layer: layer, name: layer.options.layerId })
    }

    return renderObjects(layer, objects, focusStyles)
}
