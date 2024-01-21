import * as L from "leaflet"
import { getInitialMapState, getMapState, parseMapState, setMapState } from "../_map-utils.js"
import { updateNavbarAndHash } from "../_navbar.js"
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
 * @param {HTMLDivElement} container The container element
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

    // On hash change, update the map view
    const onHashChange = () => {
        // TODO: check if no double setMapState triggered
        console.debug("onHashChange", location.hash)
        let newState = parseMapState(location.hash)

        // Get the current state if empty/invalid and replace the hash
        if (!newState) {
            newState = getMapState(map)
            updateNavbarAndHash(newState)
        }

        // Change the map view
        setMapState(map, newState)
    }

    // On base layer change, limit max zoom and zoom to max if needed
    const onBaseLayerChange = ({ layer }) => {
        const maxZoom = layer.options.maxZoom
        map.setMaxZoom(maxZoom)
        if (map.getZoom() > maxZoom) map.setZoom(maxZoom)
    }

    // On map state change, update the navbar and hash
    const onMapStateChange = () => updateNavbarAndHash(getMapState(map))

    // Listen for events
    window.addEventListener("hashchange", onHashChange)
    map.addEventListener("baselayerchange", onBaseLayerChange)
    map.addEventListener("zoomend moveend baselayerchange overlaylayerchange", onMapStateChange)

    // TODO: support this on more maps
    // Initialize map state after configuring events
    const initialMapState = getInitialMapState(map)
    setMapState(map, initialMapState, { animate: false })

    return map
}
