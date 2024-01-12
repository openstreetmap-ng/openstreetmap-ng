import { DataLayer } from "./_layers.js"

let focusLayer = null

const focusLayerFactory = () => {
    const layer = new DataLayer()
    layer.options.layerCode = ""
    layer.options.layerId = "focus"
    return layer
}

// Focus an object on the map and return its layer
// To unfocus, pass null as the object
export const focusMapObject = (map, object) => {
    // Create the focus layer if it doesn't exist
    // Also clear the layer before focusing new data
    if (!focusLayer) {
        focusLayer = focusLayerFactory()
        map.addLayer(focusLayer)
    } else {
        focusLayer.clearLayers()
    }

    return object ? focusLayer.addData([object])[0] : null
}
