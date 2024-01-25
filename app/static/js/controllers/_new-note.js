import * as L from "leaflet"
import { getActionSidebar, switchActionSidebar } from "../_action-sidebar.js"
import { getMapState, setMapState } from "../_map-utils.js"
import { qsParse } from "../_qs.js"
import { routerNavigate } from "../_router.js"
import { configureStandardForm } from "../_standard-form.js"
import { getPageTitle } from "../_title.js"
import { isLatitude, isLongitude } from "../_utils.js"
import { getOverlayLayerById } from "../leaflet/_layers.js"
import { getMarkerIcon } from "../leaflet/_utils.js"

/**
 * Create a new new note controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getNewNoteController = (map) => {
    const sidebar = getActionSidebar("export")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const form = sidebar.querySelector("form")
    const lonInput = form.querySelector("input[name=lon]")
    const latInput = form.querySelector("input[name=lat]")

    // Null values until initialized
    let marker = null
    let halo = null

    // On marker drag start, remove the halo
    const onMarkerDragStart = () => {
        map.removeLayer(halo)
    }

    // On marker drag end, update the form's coordinates and add the halo
    const onMarkerDragEnd = () => {
        const latLng = marker.getLatLng()
        lonInput.value = latLng.lng
        latInput.value = latLng.lat

        halo.setLatLng(latLng)
        map.addLayer(halo)
    }

    // On success callback, enable notes layer and navigate to the new note
    const onFormSuccess = (data) => {
        const state = getMapState(map)
        const notesLayerCode = getOverlayLayerById("notes").options.layerCode
        if (!state.layersCode.includes(notesLayerCode)) {
            state.layersCode += notesLayerCode
            setMapState(map, state)
        }

        routerNavigate(`/note/${data.noteId}`)
    }

    // Listen for events
    configureStandardForm(form, onFormSuccess)

    return {
        load: () => {
            form.reset()
            switchActionSidebar("new-note")
            document.title = getPageTitle(sidebarTitle)

            if (!marker) {
                let center = map.getCenter()

                // Allow default location setting via URL search parameters
                const searchParams = qsParse(location.search.substring(1))
                if (searchParams.lon && searchParams.lat) {
                    const lon = parseFloat(searchParams.lon)
                    const lat = parseFloat(searchParams.lat)

                    if (isLongitude(lon) && isLatitude(lat)) {
                        center = L.latLng(lat, lon)
                    }
                }

                marker = L.marker(center, {
                    icon: getMarkerIcon("new", false),
                    draggable: true,
                    autoPan: true,
                })

                halo = L.circleMarker(center, getOverlayLayerById("notes").options.styles.halo)

                marker.addEventListener("dragstart", onMarkerDragStart)
                marker.addEventListener("dragend", onMarkerDragEnd)
            } else {
                marker.setLatLng(map.getCenter())
            }

            map.addLayer(marker)

            // Initial update to set the inputs and add the halo
            onMarkerDragEnd()
        },
        unload: () => {
            map.removeLayer(marker)
            map.removeLayer(halo)
        },
    }
}
