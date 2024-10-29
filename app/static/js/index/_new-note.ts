import * as L from "leaflet"
import { qsParse } from "../_qs"
import { configureStandardForm } from "../_standard-form"
import { getPageTitle } from "../_title"
import { isLatitude, isLongitude } from "../_utils"
import { focusMapObject, focusStyles } from "../leaflet/_focus-layer"
import { type LayerId, getLayerData, getOverlayLayerById } from "../leaflet/_layers"
import { getMapState, setMapState } from "../leaflet/_map-utils"
import { setNewNoteButtonState } from "../leaflet/_new-note-control"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"
import { routerNavigateStrict } from "./_router"

/** Create a new new note controller */
export const getNewNoteController = (map: L.Map): IndexController => {
    const sidebar = getActionSidebar("new-note")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const form = sidebar.querySelector("form")
    const lonInput = form.elements.namedItem("lon") as HTMLInputElement
    const latInput = form.elements.namedItem("lat") as HTMLInputElement
    const commentInput = form.elements.namedItem("text") as HTMLInputElement
    const submitButton = form.querySelector("button[type=submit]")

    let halo: L.CircleMarker | null = null
    let marker: L.Marker | null = null

    /** On comment input, update the button state */
    const onCommentInput = () => {
        const hasValue = commentInput.value.trim().length > 0
        submitButton.disabled = !hasValue
    }
    commentInput.addEventListener("input", onCommentInput)

    configureStandardForm(
        form,
        ({ note_id }) => {
            // On success callback, navigate to the new note and simulate map move (reload notes layer)
            map.panTo(map.getCenter(), { animate: false })
            routerNavigateStrict(`/note/${note_id}`)
        },
        () => {
            // On client validation, update the form's coordinates
            const latLng = marker.getLatLng()
            lonInput.value = latLng.lng.toString()
            latInput.value = latLng.lat.toString()
            return null
        },
    )

    return {
        load: () => {
            form.reset()
            switchActionSidebar(map, "new-note")
            document.title = getPageTitle(sidebarTitle)

            let center = map.getCenter()

            // Allow default location setting via URL search parameters
            const searchParams = qsParse(location.search.substring(1))
            if (searchParams.lon && searchParams.lat) {
                const lon = Number.parseFloat(searchParams.lon)
                const lat = Number.parseFloat(searchParams.lat)
                if (isLongitude(lon) && isLatitude(lat)) {
                    center = L.latLng(lat, lon)
                }
            }

            if (halo) console.error("Halo already exists")

            halo = focusMapObject(map, {
                type: "note",
                id: null,
                lon: center.lng,
                lat: center.lat,
                icon: "new",
                draggable: true,
            })[0] as L.CircleMarker

            marker = (halo as any).marker

            // On marker drag start, hide the halo
            marker.addEventListener("dragstart", () => {
                halo.setStyle({
                    opacity: 0,
                    fillOpacity: 0,
                })
            })

            // On marker drag end, update the form's coordinates and show the halo
            marker.addEventListener("dragend", () => {
                const latLng = marker.getLatLng()
                halo.setLatLng(latLng)
                halo.setStyle({
                    opacity: focusStyles.noteHalo.opacity,
                    fillOpacity: focusStyles.noteHalo.fillOpacity,
                })
            })

            // Enable notes layer to prevent duplicates
            const state = getMapState(map)
            const notesLayerCode = getLayerData(getOverlayLayerById("notes" as LayerId)).layerCode
            if (!state.layersCode.includes(notesLayerCode)) {
                state.layersCode += notesLayerCode
                setMapState(map, state)
            }

            // Initial update
            onCommentInput()
            setNewNoteButtonState(true)
        },
        unload: () => {
            setNewNoteButtonState(false)
            focusMapObject(map, null)
            halo = null
            marker = null
        },
    }
}
