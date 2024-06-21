import * as L from "leaflet"
import { mapQueryAreaMaxSize } from "../_config.js"
import "../_types.js"
import { routerNavigateStrict } from "../index/_router.js"
import { getOverlayLayerById } from "./_layers.js"
import { renderObjects } from "./_object-render.js"
import { getLatLngBoundsSize } from "./_utils.js"

// TODO: standard alert
const maxDataLayerElements = 2000

export const dataStyles = {
    element: {
        color: "#3388FF",
        weight: 3,
        opacity: 1,
        fillOpacity: 0.4,
        interactive: true,
    },
}

/**
 * Configure the data layer for the given map
 * @param {L.Map} map Leaflet map
 * @returns {void}
 */
export const configureDataLayer = (map) => {
    const dataLayer = getOverlayLayerById("data")
    let abortController = null
    let renderedBounds = null

    /**
     * On layer click, navigate to the object page
     * @param {L.LeafletMouseEvent} event
     * @returns {void}
     */
    const onLayerClick = (event) => {
        const layer = event.target
        const object = layer.object
        routerNavigateStrict(`/${object.type}/${object.id}`)
    }

    /**
     * On map update, fetch the elements in view and update the data layer
     * @returns {void}
     */
    const onMapZoomOrMoveEnd = () => {
        // Skip if the notes layer is not visible
        if (!map.hasLayer(dataLayer)) return

        // Abort any pending request
        if (abortController) abortController.abort()
        abortController = new AbortController()

        const viewBounds = map.getBounds()

        // Skip updates if the view is satisfied
        if (renderedBounds?.contains(viewBounds)) return

        // Pad the bounds to reduce refreshes
        const bounds = viewBounds.pad(0.3)

        // Skip updates if the area is too big
        const area = getLatLngBoundsSize(bounds)
        if (area > mapQueryAreaMaxSize) return

        const minLon = bounds.getWest()
        const minLat = bounds.getSouth()
        const maxLon = bounds.getEast()
        const maxLat = bounds.getNorth()

        fetch(`/api/web/map?bbox=${minLon},${minLat},${maxLon},${maxLat}`, {
            method: "GET",
            mode: "same-origin",
            cache: "no-store", // request params are too volatile to cache
            signal: abortController.signal,
            priority: "high",
        })
            .then(async (resp) => {
                if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)

                const elements = await resp.json()
                const group = L.layerGroup()
                const renderLayers = renderObjects(group, elements, dataStyles, { renderAreas: false })

                dataLayer.clearLayers()
                if (elements.length) dataLayer.addLayer(group)
                renderedBounds = bounds

                // Listen for events
                for (const layer of renderLayers) layer.addEventListener("click", onLayerClick)
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch map data", error)
                dataLayer.clearLayers()
            })
    }

    /**
     * On overlay add, update the data layer
     * @param {L.LayersControlEvent} event
     * @returns {void}
     */
    const onOverlayAdd = ({ name }) => {
        if (name !== "data") return

        // Listen for events and run initial update
        map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        onMapZoomOrMoveEnd()
    }

    /**
     * On overlay remove, abort any pending request and clear the data layer
     * @param {L.LayersControlEvent} event
     * @returns {void}
     */
    const onOverlayRemove = ({ name }) => {
        if (name !== "data") return

        map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        if (abortController) abortController.abort()
        abortController = null
        renderedBounds = null
        dataLayer.clearLayers()
    }

    // Listen for events
    map.addEventListener("overlayadd", onOverlayAdd)
    map.addEventListener("overlayremove", onOverlayRemove)
}
