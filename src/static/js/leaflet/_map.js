import * as L from "leaflet"
import { getBaseLayerById, getOverlayLayerById } from "./_layers.js"

const getMainMap = (container) => {
    const map = L.map(container, {})

    // Configure layers
    const gpsLayer = getOverlayLayerById("gps")
    const dataLayer = getOverlayLayerById("data")
    const noteLayer = getOverlayLayerById("note")

    // TODO: finish configuration
    // TOOD: get/set last state
    // TODO: map.invalidateSize({ pan: false }) on sidebar-content

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
