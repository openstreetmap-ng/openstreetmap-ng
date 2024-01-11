import * as L from "leaflet"
import { getBaseLayerById, getOverlayLayerById } from "./_layers.js"

const getPrimaryMap = (container) => {
    const map = L.map(container, {})

    // Configure layers
    const gpsLayer = getOverlayLayerById("gps")
    const dataLayer = getOverlayLayerById("data")
    const noteLayer = getOverlayLayerById("note")
    // TODO: finish configuration
    // TOOD: get/set last state

    // On layer add, limit max zoom if it's a base layer
    const onLayerAdd = ({ layer }) => {
        if (getBaseLayerById(layer.options.layerId)) {
            map.setMaxZoom(layer.options.maxZoom)
        }
    }

    // Listen for events
    map.addEventListener("layeradd", onLayerAdd)

    return map
}
