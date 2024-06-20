import * as L from "leaflet"
import "../_types.js"
import { getOverlayLayerById } from "./_layers.js"
import { renderObjects } from "./_object-render.js"
import { getLatLngBoundsSize } from "./_utils.js"

export const focusStyles = {
    changeset: {
        pane: "focus",
        color: "#F90",
        weight: 3,
        opacity: 1,
        fillColor: "#FFFFAF",
        fillOpacity: 0,
        interactive: false,
    },
    element: {
        pane: "focus",
        color: "#F60",
        weight: 4,
        opacity: 1,
        fillOpacity: 0.5,
        interactive: false,
    },
    note: {
        pane: "focus",
    },
    noteHalo: {
        radius: 20,
        color: "#F60",
        weight: 2.5,
        opacity: 1,
        fillOpacity: 0.5,
        interactive: false,
    },
}

let paneCreated = false

/**
 * Focus an object on the map and return its layer.
 * To unfocus, pass null as the object.
 * @param {L.Map} map Leaflet map
 * @param {OSMObject|null} object Object to focus
 * @param {object} options Options
 * @param {boolean} options.fitBounds Fit the map to the focused object
 * @param {number} options.padBounds Amount of padding to add to the bounds
 * @param {number} options.maxZoom Maximum zoom level to focus on
 * @returns {L.Layer[]} The layers of the focused object
 */
export const focusMapObject = (map, object, options) => {
    console.debug("focusMapObject", object)

    if (object) {
        return focusManyMapObjects(map, [object], options)
    }

    focusManyMapObjects(map, [], options)
    return []
}

/**
 * Focus many objects on the map and return their layers.
 * To unfocus, pass an empty array as the objects.
 * @param {L.Map} map Leaflet map
 * @param {OSMObject[]} objects Objects to focus
 * @param {object} options Options
 * @param {boolean} options.fitBounds Fit the map to the focused objects
 * @param {number} options.padBounds Amount of padding to add to the bounds
 * @param {number} options.maxZoom Maximum zoom level to focus on
 * @returns {L.Layer[]} The layers of the focused objects
 */
export const focusManyMapObjects = (map, objects, options) => {
    console.debug("focusManyMapObjects", objects.length)

    const focusLayer = getOverlayLayerById("focus")

    // Always clear the focus layer
    focusLayer.clearLayers()

    // If there are no objects to focus, remove the focus layer
    if (!objects.length) {
        if (map.hasLayer(focusLayer)) {
            console.debug("Removing overlay layer", focusLayer.options.layerId)
            map.removeLayer(focusLayer)

            // Trigger the overlayremove event
            // https://leafletjs.com/reference.html#map-overlayremove
            // https://leafletjs.com/reference.html#layerscontrolevent
            map.fire("overlayremove", { layer: focusLayer, name: focusLayer.options.layerId })
        }

        return []
    }

    // Create the focus layer if it doesn't exist
    if (!map.hasLayer(focusLayer)) {
        if (!paneCreated) {
            console.debug("Creating focus pane")
            map.createPane("focus")
            paneCreated = true
        }
        console.debug("Adding overlay layer", focusLayer.options.layerId)
        map.addLayer(focusLayer)

        // Trigger the overlayadd event
        // https://leafletjs.com/reference.html#map-overlayadd
        // https://leafletjs.com/reference.html#layerscontrolevent
        map.fire("overlayadd", { layer: focusLayer, name: focusLayer.options.layerId })
    }

    const layers = renderObjects(focusLayer, objects, focusStyles)

    // Focus on the layers if they are offscreen
    if (layers.length && (options?.fitBounds ?? true)) {
        const latLngBounds = layers.reduce((bounds, layer) => bounds.extend(getLayerBounds(layer)), L.latLngBounds())
        const latLngBoundsPadded = options?.padBounds ? latLngBounds.pad(options.padBounds) : latLngBounds
        const mapBounds = map.getBounds()

        const maxZoom = options?.maxZoom ?? 18
        const currentZoom = map.getZoom()
        const fitMaxZoom = maxZoom >= currentZoom ? maxZoom : null

        if (!mapBounds.contains(latLngBounds)) {
            console.debug("Fitting map to", layers.length, "focus layers with zoom", fitMaxZoom, "(offscreen)")
            map.fitBounds(latLngBoundsPadded, { maxZoom: fitMaxZoom, animate: false })
        } else {
            const latLngSize = getLatLngBoundsSize(latLngBounds)
            const mapBoundsSize = getLatLngBoundsSize(mapBounds)
            const proportion = latLngSize / mapBoundsSize
            if (proportion > 0 && proportion < 0.00035) {
                console.debug("Fitting map to", layers.length, "focus layers with zoom", fitMaxZoom, "(small)")
                map.fitBounds(latLngBoundsPadded, { maxZoom: fitMaxZoom, animate: false })
            }
        }
    }

    return layers
}

const getLayerBounds = (layer) => {
    if (layer.getBounds) {
        return layer.getBounds()
    }
    if (layer.getLatLng) {
        return L.latLngBounds([layer.getLatLng()])
    }
    console.warn("Focus layer has no bounds", layer)
    return L.latLngBounds()
}
