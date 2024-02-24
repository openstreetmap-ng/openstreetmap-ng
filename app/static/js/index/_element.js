import * as L from "leaflet"
import { parseElements } from "../_format07.js"
import { getPageTitle } from "../_title.js"
import { focusMapObject } from "../leaflet/_focus-layer-util.js"
import { getBaseFetchController } from "./_base-fetch.js"

/**
 * Create a new element controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getElementController = (map) => {
    const onLoaded = (sidebarContent) => {
        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")
        const sidebarTitle = sidebarTitleElement.textContent
        // TODO: (version X) in title

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
            if (!map.getBounds().contains(layersBounds)) {
                map.fitBounds(layersBounds, { animate: false })
            }
        }
    }

    const base = getBaseFetchController(map, "element", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = ({ type, id, version }) => {
        const url = `/api/web/partial/element/${type}/${id}${version ? `/version/${version}` : ""}`
        baseLoad({ url })
    }

    base.unload = () => {
        focusMapObject(map, null)
        baseUnload()
    }

    return base
}
