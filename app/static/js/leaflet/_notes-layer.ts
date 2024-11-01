import * as L from "leaflet"
import { noteQueryAreaMaxSize } from "../_config"

import { fromBinary } from "@bufbuild/protobuf"
import { routerNavigateStrict } from "../index/_router"
import { RenderNotesDataSchema } from "../proto/shared_pb"
import { type LayerId, getOverlayLayerById } from "./_layers"
import { getLatLngBoundsSize, getMarkerIcon } from "./_utils"

const notesLayerId = "notes" as LayerId

/** Configure the notes layer for the given map */
export const configureNotesLayer = (map: L.Map): void => {
    const notesLayer = getOverlayLayerById(notesLayerId) as L.FeatureGroup
    let abortController: AbortController | null = null

    /** On marker click, navigate to the note */
    const onMarkerClick = (event: L.LeafletMouseEvent): void => {
        const noteId = event.target.noteId
        routerNavigateStrict(`/note/${noteId}`)
    }

    /** On map update, fetch the notes and update the notes layer */
    const onMapZoomOrMoveEnd = (): void => {
        // Skip if the notes layer is not visible
        if (!map.hasLayer(notesLayer)) return

        // Abort any pending request
        if (abortController) abortController.abort()
        abortController = new AbortController()

        // Skip updates if the area is too big
        const bounds = map.getBounds()
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

                const buffer = await resp.arrayBuffer()
                const notes = fromBinary(RenderNotesDataSchema, new Uint8Array(buffer)).notes
                const markers: L.Marker[] = []
                for (const note of notes) {
                    const marker = L.marker(L.latLng(note.point.lat, note.point.lon), {
                        icon: getMarkerIcon(note.open ? "open" : "closed", false),
                        title: note.text,
                        opacity: 0.8,
                    })
                    // @ts-ignore
                    marker.noteId = note.id
                    marker.addEventListener("click", onMarkerClick)
                    markers.push(marker)
                }

                notesLayer.clearLayers()
                notesLayer.addLayer(L.layerGroup(markers))
                console.debug("Notes layer showing", markers.length, "notes")
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch notes", error)
                notesLayer.clearLayers()
            })
    }

    // On overlay add, update the notes layer
    map.addEventListener("overlayadd", ({ name }: L.LayersControlEvent): void => {
        if (name !== notesLayerId) return
        // Listen for events and run initial update
        map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        onMapZoomOrMoveEnd()
    })

    // On overlay remove, abort any pending request and clear the notes layer
    map.addEventListener("overlayremove", ({ name }: L.LayersControlEvent): void => {
        if (name !== notesLayerId) return
        map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        if (abortController) abortController.abort()
        abortController = null
        notesLayer.clearLayers()
    })
}
