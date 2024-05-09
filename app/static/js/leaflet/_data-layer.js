import * as L from "leaflet"
import { mapQueryAreaMaxSize } from "../_config.js"
import { parseElements } from "../_format07.js"
import "../_types.js"
import { routerNavigateStrict } from "../index/_router.js"
import { getOverlayLayerById } from "./_layers.js"
import { renderObjects } from "./_object-render.js"
import { getLatLngBoundsSize } from "./_utils.js"

// TODO: standard alert
// function displayFeatureWarning(count, limit, add, cancel) {
//     $("#browse_status").html(
//       $("<div>").append(
//         $("<div class='d-flex'>").append(
//           $("<h2 class='flex-grow-1 text-break'>")
//             .text(I18n.t("browse.start_rjs.load_data")),
//           $("<div>").append(
//             $("<button type='button' class='btn-close'>")
//               .attr("aria-label", I18n.t("javascripts.close"))
//               .click(cancel))),
//         $("<p class='alert alert-warning'>")
//           .text(I18n.t("browse.start_rjs.feature_warning", { num_features: count, max_features: limit })),
//         $("<input type='submit' class='btn btn-primary'>")
//           .val(I18n.t("browse.start_rjs.load_data"))
//           .click(add)));
//   }
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
        console.debug("onLayerClick", object)
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

        // TODO: handle 180th meridian: send 2 requests

        const bounds = map.getBounds()

        // Skip updates if the view is satisfied
        if (renderedBounds?.contains(bounds)) return

        // Skip updates if the area is too big
        const area = getLatLngBoundsSize(bounds)
        if (area > mapQueryAreaMaxSize) return

        const minLon = bounds.getWest()
        const minLat = bounds.getSouth()
        const maxLon = bounds.getEast()
        const maxLat = bounds.getNorth()

        fetch(`/api/0.7/map?bbox=${minLon},${minLat},${maxLon},${maxLat}`, {
            method: "GET",
            mode: "same-origin",
            cache: "no-store", // request params are too volatile to cache
            signal: abortController.signal,
            priority: "high",
        })
            .then(async (resp) => {
                if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)

                const data = await resp.json()
                const elementMap = parseElements(data)
                const elements = [
                    ...elementMap.relation.values(),
                    ...elementMap.way.values(),
                    ...elementMap.node.values(),
                ]

                const group = L.layerGroup()
                const renderLayers = renderObjects(group, elements, dataStyles, { renderAreas: false })

                dataLayer.clearLayers()
                if (elements.length) dataLayer.addLayer(group)
                renderedBounds = bounds

                // Listen for events
                for (const layer of renderLayers) {
                    layer.addEventListener("click", onLayerClick)
                }
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
        // Handle only the data layer
        if (name !== "data") return
        onMapZoomOrMoveEnd()
    }

    /**
     * On overlay remove, abort any pending request and clear the data layer
     * @param {L.LayersControlEvent} event
     * @returns {void}
     */
    const onOverlayRemove = ({ name }) => {
        // Handle only the data layer
        if (name !== "data") return

        if (abortController) abortController.abort()
        abortController = null
        renderedBounds = null
        dataLayer.clearLayers()
    }

    // Listen for events
    map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
    map.addEventListener("overlayadd", onOverlayAdd)
    map.addEventListener("overlayremove", onOverlayRemove)
}
