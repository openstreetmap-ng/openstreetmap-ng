import * as L from "leaflet"
import { configureStandardForm } from "../_standard-form.js"
import { getPageTitle } from "../_title.js"
import { getOverlayLayerById } from "../leaflet/_layers.js"
import { getMarkerIcon } from "../leaflet/_utils.js"
import { getBaseFetchController } from "./_base_fetch.js"

/**
 * Create a new new note controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getNoteController = (map) => {
    // Null values until initialized
    // Marker is always removed because it changes depending on open/closed
    let marker = null
    let halo = null

    const onLoaded = (sidebarContent) => {
        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")
        const sidebarTitle = sidebarTitleElement.textContent
        const form = sidebarContent.querySelector("form")

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        // Get params
        const params = JSON.parse(sidebarTitleElement.dataset.params)
        const paramsId = params.id
        const lon = params.lon
        const lat = params.lat
        const closedAt = params.closedAt
        const isOpen = closedAt === null

        // Display marker and halo
        let center = L.latLng(lat, lon)

        // Marker is always removed because it changes depending on open/closed
        if (marker) console.warn("Marker already exists")

        marker = L.marker(center, {
            icon: getMarkerIcon(isOpen ? "open" : "closed", false),
            keyboard: false,
            interactive: false,
        })

        if (!halo) {
            halo = L.circleMarker(center, getOverlayLayerById("notes").options.styles.halo)
        } else {
            halo.setLatLng(center)
        }

        map.addLayer(halo)
        map.addLayer(marker)

        // On success callback, reload the note
        const onFormSuccess = () => {
            base.unload()
            base.load({ id: paramsId })
        }

        // Listen for events
        configureStandardForm(form, onFormSuccess)
    }

    const base = getBaseFetchController("note", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = ({ id }) => {
        const url = `/api/web/partial/note/${id}`
        baseLoad({ url })
    }

    base.unload = () => {
        // Remove marker and halo only if successfully created
        if (marker) {
            map.removeLayer(marker)
            map.removeLayer(halo)
            marker = null
        }
        baseUnload()
    }

    return base
}
