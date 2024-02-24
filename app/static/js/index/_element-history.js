import * as L from "leaflet"
import { parseElements } from "../_format07.js"
import { getPageTitle } from "../_title.js"
import { focusMapObject } from "../leaflet/_focus-layer-util.js"
import { getBaseFetchController } from "./_base-fetch.js"

/**
 * Create a new element history controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getElementHistoryController = (map) => {
    const onLoaded = (sidebarContent) => {
        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")
        const sidebarTitle = sidebarTitleElement.textContent

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        // Get params
        const params = JSON.parse(sidebarTitleElement.dataset.params)
        const mainElementType = params.type
        const mainElementId = params.id
        const elements = params.elements

        // Not all elements are focusable (e.g., non-latest ways and relations)
        if (elements?.length) {
            const elementMap = parseElements(elements)
            const mainElement = elementMap[mainElementType].get(mainElementId)
            const layers = focusMapObject(map, mainElement)
            const layersBounds = L.featureGroup(layers).getBounds()

            // Focus on the elements if they're offscreen
            // TODO: padding
            if (!map.getBounds().contains(layersBounds)) {
                map.fitBounds(layersBounds, { animate: false })
            }
        }
    }

    const base = getBaseFetchController(map, "element-history", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = ({ type, id }) => {
        const url = `/api/web/partial/element/${type}/${id}/history`
        baseLoad({ url })
    }

    base.unload = () => {
        focusMapObject(map, null)
        baseUnload()
    }

    return base
}
