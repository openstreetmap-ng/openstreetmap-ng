import { getActionSidebar, switchActionSidebar } from "@index/_action-sidebar"
import { routerNavigateStrict } from "@index/router"
import { isLatitude, isLongitude } from "@lib/coords"
import { setNewNoteButtonState } from "@lib/map/controls/new-note"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import { type LayerId, layersConfig } from "@lib/map/layers/layers"
import { getMarkerIconElement, MARKER_ICON_ANCHOR } from "@lib/map/marker"
import { getMapState, setMapState } from "@lib/map/state"
import { IdResponseSchema, NoteStatus } from "@lib/proto/shared_pb"
import { qsParse } from "@lib/qs"
import { configureStandardForm } from "@lib/standard-form"
import { setPageTitle } from "@lib/title"
import { LngLat, type Map as MaplibreMap, Marker } from "maplibre-gl"

const NOTES_LAYER_ID = "notes" as LayerId
const THEME_COLOR = "#f60"
const focusPaint: FocusLayerPaint = {
    "circle-radius": 20,
    "circle-color": THEME_COLOR,
    "circle-opacity": 0.5,
    "circle-stroke-color": THEME_COLOR,
    "circle-stroke-opacity": 1,
    "circle-stroke-width": 2.5,
}

export const getNewNoteController = (map: MaplibreMap) => {
    const sidebar = getActionSidebar("new-note")
    const sidebarTitle = sidebar.querySelector(".sidebar-title")!.textContent
    const form = sidebar.querySelector("form")!
    const lonInput = form.querySelector("input[name=lon]")!
    const latInput = form.querySelector("input[name=lat]")!
    const commentInput = form.querySelector("textarea[name=text]")!
    const submitButton = form.querySelector("button[type=submit]")!

    let marker: Marker | null = null

    const updateButtonState = () => {
        const hasValue = commentInput.value.trim().length > 0
        submitButton.disabled = !hasValue
    }
    commentInput.addEventListener("input", updateButtonState)

    configureStandardForm(
        form,
        (data) => {
            // On success callback, navigate to the new note and reload the notes layer
            console.debug("NewNote: Created", data.id)
            map.fire("reloadnoteslayer")
            routerNavigateStrict(`/note/${data.id}`)
        },
        { protobuf: IdResponseSchema },
    )

    return {
        load: () => {
            form.reset()
            switchActionSidebar(map, sidebar)
            setPageTitle(sidebarTitle)

            // Allow default location setting via URL search parameters
            let center: LngLat | undefined
            const searchParams = qsParse(window.location.search)
            if (searchParams.lon && searchParams.lat) {
                const lon = Number.parseFloat(searchParams.lon)
                const lat = Number.parseFloat(searchParams.lat)
                if (isLongitude(lon) && isLatitude(lat)) {
                    center = new LngLat(lon, lat)
                }
            }

            marker = new Marker({
                anchor: MARKER_ICON_ANCHOR,
                element: getMarkerIconElement("new", false),
                draggable: true,
            })
                .setLngLat(center ?? map.getCenter())
                .addTo(map)

            const onDragEnd = () => {
                if (!marker) return

                // Focus halo and update inputs
                const lngLat = marker.getLngLat()
                focusObjects(
                    map,
                    [
                        {
                            type: "note",
                            id: null,
                            geom: [lngLat.lng, lngLat.lat],
                            status: NoteStatus.open,
                            text: "",
                        },
                    ],
                    focusPaint,
                    null,
                    false,
                )
                lonInput.value = lngLat.lng.toString()
                latInput.value = lngLat.lat.toString()
            }

            marker.on("dragstart", () => focusObjects(map)) // hide halo
            marker.on("dragend", onDragEnd) // show halo

            // Initial update
            onDragEnd()
            updateButtonState()
            setNewNoteButtonState(true)

            // Enable notes layer to prevent duplicates
            const state = getMapState(map)
            const notesLayerCode = layersConfig.get(NOTES_LAYER_ID)!.layerCode!
            if (!state.layersCode.includes(notesLayerCode)) {
                state.layersCode += notesLayerCode
                setMapState(map, state)
            }
        },
        unload: () => {
            setNewNoteButtonState(false)
            focusObjects(map)
            marker!.remove()
            marker = null
        },
    }
}
