import * as L from "leaflet"
import { getLastMapState } from "../_local-storage.js"
import { setMapState } from "../_map-utils.js"
import { getLocateControl } from "./_locate.js"
import { getNewNoteControl } from "./_new-note.js"
import { getQueryFeaturesControl } from "./_query-features.js"
import { getLayersSidebarToggleButton } from "./_sidebar-toggle-button-layers.js"
import { getLegendSidebarToggleButton } from "./_sidebar-toggle-button-legend.js"
import { getShareSidebarToggleButton } from "./_sidebar-toggle-button-share.js"
import { getZoomControl } from "./_zoom.js"

/**
 * Get the main map
 * @param {HTMLElement} container The container element
 * @returns {L.Map} The map
 */
export const getMainMap = (container) => {
    const map = L.map(container, {
        zoomControl: false,
    })

    // Disable Leaflet's attribution prefix
    map.attributionControl.setPrefix(false)

    // Add native controls
    map.addControl(L.control.scale({ updateWhenIdle: true }))

    // Add custom controls
    map.addControl(getZoomControl())
    map.addControl(getLocateControl())
    map.addControl(getLayersSidebarToggleButton())
    map.addControl(getLegendSidebarToggleButton())
    map.addControl(getShareSidebarToggleButton())
    map.addControl(getNewNoteControl())
    map.addControl(getQueryFeaturesControl())

    // TODO: finish configuration
    // TOOD: get/set last state
    // TODO: map.invalidateSize({ pan: false }) on sidebar-content

    // On base layer change, limit max zoom and zoom to max if needed
    const onBaseLayerChange = ({ layer }) => {
        const maxZoom = layer.options.maxZoom
        map.setMaxZoom(maxZoom)
        if (map.getZoom() > maxZoom) map.setZoom(maxZoom)
    }

    // Listen for events
    map.addEventListener("baselayerchange", onBaseLayerChange)

    // Initialize map state
    const lastMapState = getLastMapState()
    if (lastMapState) setMapState(map, lastMapState, { animate: false })

    return map
}
