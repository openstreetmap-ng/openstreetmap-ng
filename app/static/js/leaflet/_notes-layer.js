import * as L from "leaflet"
import { noteQueryAreaMaxSize } from "../_config.js"
import "../_types.js"
import { routerNavigateStrict } from "../index/_router.js"
import { getOverlayLayerById } from "./_layers.js"
import { getLatLngBoundsSize, getMarkerIcon } from "./_utils.js"

/**
 * Configure the notes layer for the given map
 * @param {L.Map} map Leaflet map
 * @returns {void}
 */
export const configureNotesLayer = (map) => {
    const notesLayer = getOverlayLayerById("notes")
    let abortController = null

    /**
     * On marker click, navigate to the note
     * @param {L.LeafletMouseEvent} event
     * @returns {void}
     */
    const onMarkerClick = (event) => {
        const marker = event.target
        const noteId = marker.noteId
        routerNavigateStrict(`/note/${noteId}`)
    }

    /**
     * On map update, fetch the notes and update the notes layer
     * @returns {void}
     */
    const onMapZoomOrMoveEnd = () => {
        // Skip if the notes layer is not visible
        if (!map.hasLayer(notesLayer)) return

        // Abort any pending request
        if (abortController) abortController.abort()
        abortController = new AbortController()

        const bounds = map.getBounds()

        // Skip updates if the area is too big
        const area = getLatLngBoundsSize(bounds)
        if (area > noteQueryAreaMaxSize) return

        const minLon = bounds.getWest()
        const minLat = bounds.getSouth()
        const maxLon = bounds.getEast()
        const maxLat = bounds.getNorth()

        fetch(`/api/web/note/map?bbox=${minLon},${minLat},${maxLon},${maxLat}`, {
            method: "GET",
            mode: "same-origin",
            cache: "no-store", // request params are too volatile to cache
            signal: abortController.signal,
            priority: "high",
        })
            .then(async (resp) => {
                if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)

                const notes = await resp.json()
                const markers = []
                for (const note of notes) {
                    const marker = L.marker(note.geom, {
                        icon: getMarkerIcon(note.open ? "open" : "closed", false),
                        title: note.text,
                        opacity: 0.8,
                    })
                    marker.noteId = note.id
                    marker.addEventListener("click", onMarkerClick)
                    markers.push(marker)
                }

                notesLayer.clearLayers()
                if (markers.length) notesLayer.addLayer(L.layerGroup(markers))
                console.debug("Notes layer showing", markers.length, "notes")
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch notes", error)
                notesLayer.clearLayers()
            })
    }

    /**
     * On overlay add, update the notes layer
     * @param {L.LayersControlEvent} event
     * @returns {void}
     */
    const onOverlayAdd = ({ name }) => {
        if (name !== "notes") return

        // Listen for events and run initial update
        map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        onMapZoomOrMoveEnd()
    }

    /**
     * On overlay remove, abort any pending request and clear the notes layer
     * @param {L.LayersControlEvent} event
     * @returns {void}
     */
    const onOverlayRemove = ({ name }) => {
        if (name !== "notes") return

        map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        if (abortController) abortController.abort()
        abortController = null
        notesLayer.clearLayers()
    }

    // Listen for events
    map.addEventListener("overlayadd", onOverlayAdd)
    map.addEventListener("overlayremove", onOverlayRemove)
}
