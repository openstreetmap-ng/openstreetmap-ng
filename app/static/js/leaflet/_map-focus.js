import * as L from "leaflet"
import "../_types.js"
import { DataLayer } from "./_layers.js"

let focusLayer = null

/**
 * Create a new layer for focusing on a single object
 * @returns {DataLayer} The new layer
 */
const focusLayerFactory = () => {
    const layer = new DataLayer()
    layer.options.layerCode = ""
    layer.options.layerId = "focus"
    return layer
}

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
    if (focusLayer) {
        focusLayer.clearLayers()
    } else {
        focusLayer = focusLayerFactory()
        map.addLayer(focusLayer)
    }

    return focusLayer.addData(objects)
}
