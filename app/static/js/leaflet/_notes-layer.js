import * as L from "leaflet"
import { apiUrl, noteQueryAreaMaxSize } from "../_config.js"
import "../_types.js"
import { routerNavigate } from "../index/_router.js"
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
        const marker = event.propagatedFrom
        const noteId = marker.noteId
        routerNavigate(`/note/${noteId}`)
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

        // TODO: handle 180th meridian: send 2 requests

        const bounds = map.getBounds()

        // Skip updates if the area is too big
        const area = getLatLngBoundsSize(bounds)
        if (area > noteQueryAreaMaxSize) return

        const minLon = bounds.getWest()
        const minLat = bounds.getSouth()
        const maxLon = bounds.getEast()
        const maxLat = bounds.getNorth()

        fetch(`${apiUrl}/api/0.6/notes.json?bbox=${minLon},${minLat},${maxLon},${maxLat}`, {
            method: "GET",
            mode: "same-origin",
            cache: "no-store", // request params are too volatile to cache
            signal: abortController.signal,
            priority: "high",
        })
            .then(async (resp) => {
                if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)

                const data = await resp.json()
                const markers = []

                // data in GeoJSON format
                for (const feature of data.features) {
                    const [lon, lat] = feature.geometry.coordinates
                    const props = feature.properties
                    const noteId = props.id
                    const isOpen = props.status === "open"

                    const marker = L.marker(L.latLng(lat, lon), {
                        icon: getMarkerIcon(isOpen ? "open" : "closed", false),
                        title: props.comments.length ? props.comments[0].text : "",
                        opacity: 0.8,
                    })

                    marker.noteId = noteId
                    marker.addEventListener("click", onMarkerClick)
                    markers.push(marker)
                }

                notesLayer.clearLayers()
                if (markers.length) notesLayer.addLayer(L.layerGroup(markers))
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
        // Handle only the notes layer
        if (name !== "notes") return
        onMapZoomOrMoveEnd()
    }

    /**
     * On overlay remove, abort any pending request and clear the notes layer
     * @param {L.LayersControlEvent} event
     * @returns {void}
     */
    const onOverlayRemove = ({ name }) => {
        // Handle only the notes layer
        if (name !== "notes") return

        if (abortController) abortController.abort()
        abortController = null

        notesLayer.clearLayers()
    }

    // Listen for events
    map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
    map.addEventListener("overlayadd", onOverlayAdd)
    map.addEventListener("overlayremove", onOverlayRemove)
}
