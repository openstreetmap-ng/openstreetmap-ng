import * as L from "leaflet"
import { getBaseLayerById } from "./_layers.js"

export const getMarkerIcon = (color, shadow = true) => {
    let shadowUrl = null
    let shadowSize = null

    if (shadow) {
        shadowUrl = "/static/img/marker/shadow.webp"
        shadowSize = [41, 41]
    }

    return L.icon({
        iconUrl: `/static/img/marker/${color}.webp`,
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowUrl: shadowUrl,
        shadowSize: shadowSize,
    })
}

// Get the size (area in square degrees) of a LatLngBounds
export const getLatLngBoundsSize = (latLngBounds) => {
    const sw = latLngBounds.getSouthWest()
    const ne = latLngBounds.getNorthEast()
    return (ne.lng - sw.lng) * (ne.lat - sw.lat)
}

// Encode current layers to a string using layer codes
export const getMapLayersCode = (map) => {
    const layerCodes = []
    map.eachLayer((layer) => {
        if (layer.options.layerCode) layerCodes.push(layer.options.layerCode)
    })
    return layerCodes.join("")
}

// Get the base layer id of the map
export const getMapBaseLayerId = (map) => {
    let baseLayerId = null
    map.eachLayer((layer) => {
        if (getBaseLayerById(layer.options.layerId)) baseLayerId = layer.options.layerId
    })
    if (!baseLayerId) throw new Error("No base layer found")
    return baseLayerId
}

// Get the base layer instance of the map
export const getMapBaseLayer = (map) => {
    let baseLayer = null
    map.eachLayer((layer) => {
        if (getBaseLayerById(layer.options.layerId)) baseLayer = layer
    })
    if (!baseLayer) throw new Error("No base layer found")
    return baseLayer
}
