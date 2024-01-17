import * as L from "leaflet"
import { getInitialMapState, setMapState } from "../_map-utils.js"
import { qsParse } from "../_qs.js"
import { isLatitude, isLongitude } from "../_utils.js"
import { getLocateControl } from "./_locate.js"
import { getNewNoteControl } from "./_new-note.js"
import { getQueryFeaturesControl } from "./_query-features.js"
import { getLayersSidebarToggleButton } from "./_sidebar-toggle-button-layers.js"
import { getLegendSidebarToggleButton } from "./_sidebar-toggle-button-legend.js"
import { getShareSidebarToggleButton } from "./_sidebar-toggle-button-share.js"
import { getMarkerIcon } from "./_utils.js"
import { getZoomControl } from "./_zoom.js"

// TODO: map.invalidateSize({ pan: false }) on sidebar-content

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
    map.addControl(L.control.scale())

    // Add custom controls
    map.addControl(getZoomControl())
    map.addControl(getLocateControl())
    map.addControl(getLayersSidebarToggleButton())
    map.addControl(getLegendSidebarToggleButton())
    map.addControl(getShareSidebarToggleButton())
    map.addControl(getNewNoteControl())
    map.addControl(getQueryFeaturesControl())

    // Add optional map marker
    const searchParams = qsParse(location.search.substring(1))
    if (searchParams.mlon && searchParams.mlat) {
        const mlon = parseFloat(searchParams.mlon)
        const mlat = parseFloat(searchParams.mlat)
        if (isLongitude(mlon) && isLatitude(mlat)) {
            const marker = L.marker(L.latLng(mlat, mlon), {
                icon: getMarkerIcon("blue", true),
                keyboard: false,
                interactive: false,
            })
            map.addLayer(marker)
        }
    }

    // On base layer change, limit max zoom and zoom to max if needed
    const onBaseLayerChange = ({ layer }) => {
        const maxZoom = layer.options.maxZoom
        map.setMaxZoom(maxZoom)
        if (map.getZoom() > maxZoom) map.setZoom(maxZoom)
    }

    // Listen for events
    map.addEventListener("baselayerchange", onBaseLayerChange)

    // TODO: support this on more maps
    // Initialize map state after configuring events
    const initialMapState = getInitialMapState(map)
    setMapState(map, initialMapState, { animate: false })

    return map
}
