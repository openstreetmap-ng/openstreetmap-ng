import * as L from "leaflet"
import { configureActionSidebars } from "../_action-sidebar.js"
import { homePoint } from "../_config.js"
import { updateNavbarAndHash } from "../_navbar.js"
import { qsParse } from "../_qs.js"
import { isLatitude, isLongitude } from "../_utils.js"
import { getChangesetController } from "../index/_changeset.js"
import { getChangesetsHistoryController } from "../index/_changesets-history.js"
import { getElementHistoryController } from "../index/_element-history.js"
import { getElementController } from "../index/_element.js"
import { getExportController } from "../index/_export.js"
import { getIndexController } from "../index/_index.js"
import { getNewNoteController } from "../index/_new-note.js"
import { getNoteController } from "../index/_note.js"
import { getQueryFeaturesController } from "../index/_query-features.js"
import { configureRouter } from "../index/_router.js"
import { configureDataLayer } from "./_data-layer.js"
import { configureFindHomeButton } from "./_find-home-button.js"
import { getGeolocateControl } from "./_geolocate-control.js"
import {
    addControlGroup,
    disableControlClickPropagation,
    getInitialMapState,
    getMapState,
    parseMapState,
    setMapState,
} from "./_map-utils.js"
import { getNewNoteControl } from "./_new-note-control.js"
import { configureNotesLayer } from "./_notes-layer.js"
import { getQueryFeaturesControl } from "./_query-features-control.js"
import { getLayersSidebarToggleButton } from "./_sidebar-layers.js"
import { getLegendSidebarToggleButton } from "./_sidebar-legend.js"
import { getShareSidebarToggleButton } from "./_sidebar-share.js"
import { getMarkerIcon } from "./_utils.js"
import { getZoomControl } from "./_zoom-control.js"

// TODO: map.invalidateSize(false) on sidebar-content

/**
 * Get the main map instance
 * @param {HTMLDivElement} container The container element
 * @returns {L.Map} Leaflet map
 */
const getMainMap = (container) => {
    console.debug("Initializing main map")

    const map = L.map(container, {
        zoomControl: false,
    })

    // Disable Leaflet's attribution prefix
    map.attributionControl.setPrefix(false)

    // Add native controls
    map.addControl(L.control.scale())

    // Add custom controls
    addControlGroup(map, [getZoomControl(), getGeolocateControl()])
    addControlGroup(map, [
        getLayersSidebarToggleButton(),
        getLegendSidebarToggleButton(),
        getShareSidebarToggleButton(),
    ])
    addControlGroup(map, [getNewNoteControl()])
    addControlGroup(map, [getQueryFeaturesControl()])

    // Disable click propagation on controls
    disableControlClickPropagation(map)

    // Configure map handlers
    configureNotesLayer(map)
    configureDataLayer(map)
    // configureContextMenu(map)

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

/**
 * Configure the main map and all its components
 * @param {HTMLDivElement} container The container element
 * @returns {void}
 */
export const configureMainMap = (container) => {
    const map = getMainMap(container)

    // Configure here instead of navbar to avoid global script dependency (navbar is global)
    // Find home button is only available for the users with configured home location
    if (homePoint) {
        const findHomeButton = document.querySelector(".find-home")
        if (findHomeButton) configureFindHomeButton(map, findHomeButton)
    }

    configureRouter(
        new Map([
            ["/", getIndexController(map)],
            ["/export", getExportController(map)],
            ["/directions", getRoutingController(map)],
            ["/search", getSearchController(map)],
            ["/query", getQueryFeaturesController(map)],
            [
                "(?:/history(?:/(?<scope>nearby|friends))?|/user/(?<displayName>[^/]+)/history)",
                getChangesetsHistoryController(map),
            ],
            ["/note/new", getNewNoteController(map)],
            ["/note/(?<id>\\d+)", getNoteController(map)],
            ["/changeset/(?<id>\\d+)", getChangesetController(map)],
            ["/(?<type>node|way|relation)/(?<id>\\d+)(?:/history/(?<version>\\d+))?", getElementController(map)],
            ["/(?<type>node|way|relation)/(?<id>\\d+)/history", getElementHistoryController(map)],
        ]),
    )

    configureActionSidebars()
}
