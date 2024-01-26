import * as L from "leaflet"
import "../_types.js"
import { addGroupFeatures, getOverlayLayerById } from "./_layers.js"

export const focusStyles = {
    changeset: {
        color: "#FF9500",
        weight: 4,
        opacity: 1,
        fillOpacity: 0,
        interactive: false,
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
        fillOpacity: 0.5,
        interactive: false,
    },
}

let focusLayer = null

/**
 * Focus an object on the map and return its layer.
 * To unfocus, pass null as the object.
 * @param {L.Map} map Leaflet map
 * @param {OSMObject|null} object Object to focus
 * @returns {L.Layer|null} The layer of the focused object
 */
export const focusMapObject = (map, object) => {
    if (object) {
        return focusManyMapObjects(map, [object])[0]
    }

    focusManyMapObjects(map, [])
    return null
}

/**
 * Focus many objects on the map and return their layers.
 * To unfocus, pass an empty array as the objects.
 * @param {L.Map} map Leaflet map
 * @param {OSMObject[]} objects Objects to focus
 * @returns {L.Layer[]} The layers of the focused objects
 */
export const focusManyMapObjects = (map, objects) => {
    // Always clear the focus layer
    if (focusLayer) {
        focusLayer.clearLayers()
    }

    // If there are no objects to focus, remove the focus layer
    if (objects.length === 0) {
        if (focusLayer) {
            map.removeLayer(focusLayer)

            // Trigger the overlayremove event
            // https://leafletjs.com/reference.html#map-overlayremove
            // https://leafletjs.com/reference.html#layerscontrolevent
            map.fire("overlayremove", { layer: focusLayer, name: focusLayer.options.layerId })

            focusLayer = null
        }

        return []
    }

    // TODO: z-index
    // Create the focus layer if it doesn't exist
    if (!focusLayer) {
        focusLayer = getOverlayLayerById("focus")
        map.addLayer(focusLayer)

        // Trigger the overlayadd event
        // https://leafletjs.com/reference.html#map-overlayadd
        // https://leafletjs.com/reference.html#layerscontrolevent
        map.fire("overlayadd", { layer: focusLayer, name: focusLayer.options.layerId })
    }

    return addGroupFeatures(focusLayer, objects, focusStyles)
}
