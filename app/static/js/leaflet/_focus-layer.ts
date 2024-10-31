import * as L from "leaflet"

import type { OSMObject } from "../_types"
import { type LayerId, getOverlayLayerById } from "./_layers"
import { type RenderStyles, renderObjects } from "./_render-objects"
import { getLatLngBoundsSize } from "./_utils"

export interface FocusOptions {
    /** Fit the map to the focused objects */
    fitBounds?: boolean
    /** Amount of padding to add to the bounds */
    padBounds?: number
    /** Maximum zoom level to focus on */
    maxZoom?: number
    /** Whether to perform intersection check instead of containment */
    intersects?: boolean
    /** Perform a proportion check when fitting the map */
    proportionCheck?: boolean
}

const focusLayerId = "focus" as LayerId

export const focusStyles: RenderStyles = {
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
 */
export const focusMapObject = (map: L.Map, object: OSMObject | null, options?: FocusOptions): L.Layer[] => {
    if (object) {
        return focusManyMapObjects(map, [object], options)
    }
    focusManyMapObjects(map, [], options)
    return []
}

/**
 * Focus many objects on the map and return their layers.
 * To unfocus, pass an empty array as the objects.
 */
export const focusManyMapObjects = (map: L.Map, objects: OSMObject[], options?: FocusOptions): L.Layer[] => {
    const focusLayer = getOverlayLayerById(focusLayerId) as L.FeatureGroup

    // Always clear the focus layer
    focusLayer.clearLayers()

    // If there are no objects to focus, remove the focus layer
    if (!objects.length) {
        if (map.hasLayer(focusLayer)) {
            map.removeLayer(focusLayer)

            // Trigger the overlayremove event
            // https://leafletjs.com/reference.html#map-overlayremove
            // https://leafletjs.com/reference.html#layerscontrolevent
            map.fire("overlayremove", { layer: focusLayer, name: focusLayerId })
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
        map.addLayer(focusLayer)

        // Trigger the overlayadd event
        // https://leafletjs.com/reference.html#map-overlayadd
        // https://leafletjs.com/reference.html#layerscontrolevent
        map.fire("overlayadd", { layer: focusLayer, name: focusLayerId })
    }

    const layers = renderObjects(focusLayer, objects, focusStyles)

    // Focus on the layers if they are offscreen
    if (layers.length && (options?.fitBounds ?? true)) {
        let latLngBounds: L.LatLngBounds | null = null
        for (const layer of layers) {
            const layerBounds = getLayerBounds(layer)
            if (layerBounds === null) continue
            if (!latLngBounds) latLngBounds = layerBounds
            else latLngBounds.extend(layerBounds)
        }
        const latLngBoundsPadded = options?.padBounds ? latLngBounds.pad(options.padBounds) : latLngBounds
        const mapBounds = map.getBounds()

        const maxZoom = options?.maxZoom ?? 18
        const currentZoom = map.getZoom()
        const fitMaxZoom = maxZoom >= currentZoom ? maxZoom : null

        if (options?.intersects ? !mapBounds.intersects(latLngBounds) : !mapBounds.contains(latLngBounds)) {
            console.debug("Fitting map to", layers.length, "focus layers with zoom", fitMaxZoom, "(offscreen)")
            map.fitBounds(latLngBoundsPadded, { maxZoom: fitMaxZoom, animate: false })
        } else if ((options?.proportionCheck ?? true) && fitMaxZoom > currentZoom) {
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

const getLayerBounds = (layer: any): L.LatLngBounds | null => {
    if (layer.getBounds) {
        return layer.getBounds()
    }
    if (layer.getLatLng) {
        return L.latLngBounds([layer.getLatLng()])
    }
    console.warn("Focus layer has no bounds", layer)
    return null
}
