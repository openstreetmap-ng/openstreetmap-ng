import * as L from "leaflet"
import { getPageTitle } from "../_title.js"
import { getOverlayLayerById } from "../leaflet/_layers.js"
import { makeBoundsMinimumSize } from "../leaflet/_utils.js"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar.js"
import { routerNavigateStrict } from "./_router.js"

export const styles = {
    default: {
        color: "#FF9500",
        weight: 2,
        opacity: 1,
        fillColor: "#FFFFAF",
        fillOpacity: 0,
    },
    hover: {
        color: "#FF6600",
        weight: 3,
        fillOpacity: 0.4,
    },
}

/**
 * Create a new changesets history controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getChangesetsHistoryController = (map) => {
    const changesetLayer = getOverlayLayerById("changesets")
    const sidebar = getActionSidebar("changesets-history")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const entryTemplate = sidebar.querySelector("template.entry")

    let abortController = null

    // Store changesets to allow loading more
    const changesets = []
    let changesetsBBox = ""

    /**
     * On layer click, navigate to the changeset
     * @param {L.LeafletMouseEvent} event
     * @returns {void}
     */
    const onLayerClick = (event) => {
        const layer = event.target
        const changesetId = layer.changesetId
        routerNavigateStrict(`/changeset/${changesetId}`)
    }

    /**
     * On layer mouseover, highlight the changeset
     * @param {L.LeafletMouseEvent} event
     * @returns {void}
     */
    const onLayerMouseover = (event) => {
        const layer = event.target
        layer.setStyle(styles.hover)
    }

    /**
     * On layer mouseout, un-highlight the changeset
     * @param {L.LeafletMouseEvent} event
     * @returns {void}
     */
    const onLayerMouseout = (event) => {
        const layer = event.target
        layer.setStyle(styles.default)
    }

    /**
     * On map update, fetch the changesets in view and update the changesets layer
     * @returns {void}
     */
    const onMapZoomOrMoveEnd = () => {
        // Abort any pending request
        if (abortController) abortController.abort()
        abortController = new AbortController()

        const bounds = map.getBounds()
        const minLon = bounds.getWest()
        const minLat = bounds.getSouth()
        const maxLon = bounds.getEast()
        const maxLat = bounds.getNorth()
        const bbox = `${minLon},${minLat},${maxLon},${maxLat}`

        fetch(`/api/web/changeset/map?bbox=${bbox}`, {
            method: "GET",
            mode: "same-origin",
            cache: "no-store", // request params are too volatile to cache
            signal: abortController.signal,
            priority: "high",
        })
            .then(async (resp) => {
                if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)

                // Clear the changesets if the bbox changed
                if (changesetsBBox !== bbox) {
                    changesetsBBox = bbox
                    changesets.length = 0
                }

                changesets.push(...(await resp.json()))

                // Sort by bounds area (descending)
                const changesetsSorted = []
                for (const changeset of changesets) {
                    const bounds = makeBoundsMinimumSize(map, changeset.geom)
                    const boundsArea = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
                    changesetsSorted.push([changeset, bounds, boundsArea])
                }
                changesetsSorted.sort((a, b) => b[2] - a[2])

                const layers = []
                for (const [changeset, bounds] of changesetsSorted) {
                    const geom = [
                        [bounds[1], bounds[0]],
                        [bounds[3], bounds[2]],
                    ]
                    const layer = L.rectangle(geom, styles.default)
                    layer.changesetId = changeset.id
                    layer.addEventListener("mouseover", onLayerMouseover)
                    layer.addEventListener("mouseout", onLayerMouseout)
                    layer.addEventListener("click", onLayerClick)
                    layers.push(layer)
                }

                changesetLayer.clearLayers()
                if (layers.length) changesetLayer.addLayer(L.layerGroup(layers))
                console.debug("Changesets layer showing", layers.length, "changesets")
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch map data", error)
                changesetLayer.clearLayers()
                changesets.length = 0
            })
    }

    return {
        load: () => {
            switchActionSidebar(map, "changesets-history")
            document.title = getPageTitle(sidebarTitle)

            // Create the changeset layer if it doesn't exist
            if (!map.hasLayer(changesetLayer)) {
                console.debug("Adding overlay layer", changesetLayer.options.layerId)
                map.addLayer(changesetLayer)
                map.fire("overlayadd", { layer: changesetLayer, name: changesetLayer.options.layerId })
            }

            // TODO: more of this
            // Listen for events and run initial update
            map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
            onMapZoomOrMoveEnd()
        },
        unload: () => {
            map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)

            // Remove the changeset layer
            if (map.hasLayer(changesetLayer)) {
                console.debug("Removing overlay layer", changesetLayer.options.layerId)
                map.removeLayer(changesetLayer)
                map.fire("overlayremove", { layer: changesetLayer, name: changesetLayer.options.layerId })
            }

            // Clear the changeset layer
            changesetLayer.clearLayers()
            changesets.length = 0
        },
    }
}
