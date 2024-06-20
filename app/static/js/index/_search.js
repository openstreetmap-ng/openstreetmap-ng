import i18next from "i18next"
import * as L from "leaflet"
import { qsEncode, qsParse } from "../_qs.js"
import { getPageTitle } from "../_title.js"
import { focusManyMapObjects, focusMapObject } from "../leaflet/_focus-layer.js"
import { getOverlayLayerById } from "../leaflet/_layers.js"
import { getBaseFetchController } from "./_base-fetch.js"

const styles = {}

/**
 * Create a new search controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getSearchController = (map) => {
    const defaultTitle = i18next.t("site.search.search")
    const searchLayer = getOverlayLayerById("search")
    const searchInput = document.querySelector(".search-form").elements.q

    const onLoaded = (sidebarContent) => {
        const searchList = sidebarContent.querySelector(".search-list")

        // Handle no results
        if (!searchList) return

        const groupedElements = JSON.parse(searchList.dataset.leaflet)
        const results = searchList.querySelectorAll(".social-action")
        const layerGroup = L.layerGroup()

        // Iterate in reverse add layers in priority order
        for (let i = results.length - 1; i >= 0; i--) {
            const elements = groupedElements[i]
            const result = results[i]

            // On mouse enter, focus elements
            const onResultMouseover = () => {
                console.debug("onResultMouseover")
                focusManyMapObjects(map, elements, { padBounds: 0.3, maxZoom: 17 })
            }

            // On mouse leave, unfocus elements
            const onResultMouseout = () => {
                console.debug("onResultMouseout")
                focusMapObject(map, null)
            }

            // Listen for events
            result.addEventListener("mouseover", onResultMouseover)
            result.addEventListener("mouseout", onResultMouseout)

            // TODO: marker
        }

        searchLayer.clearLayers()
        if (results.length) searchLayer.addLayer(layerGroup)
        console.debug("Search layer showing", results.length, "results")
    }

    const base = getBaseFetchController(map, "search", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = () => {
        // Create the search layer if it doesn't exist
        if (!map.hasLayer(searchLayer)) {
            console.debug("Adding overlay layer", searchLayer.options.layerId)
            map.addLayer(searchLayer)
            map.fire("overlayadd", { layer: searchLayer, name: searchLayer.options.layerId })
        }

        const searchParams = qsParse(location.search.substring(1))
        const query = searchParams.q || searchParams.query || ""

        // Set page title
        document.title = getPageTitle(query || defaultTitle)

        // Set search input if unset
        if (!searchInput.value) searchInput.value = query

        // Pad the bounds to gather more local results
        const bbox = map.getBounds().pad(1).toBBoxString()

        const url = `/api/partial/search?${qsEncode({ q: query, bbox })}`
        baseLoad({ url })
    }

    base.unload = () => {
        baseUnload()

        // Remove the search layer
        if (map.hasLayer(searchLayer)) {
            console.debug("Removing overlay layer", searchLayer.options.layerId)
            map.removeLayer(searchLayer)
            map.fire("overlayremove", { layer: searchLayer, name: searchLayer.options.layerId })
        }

        // Clear the search layer
        searchLayer.clearLayers()
    }

    return base
}
