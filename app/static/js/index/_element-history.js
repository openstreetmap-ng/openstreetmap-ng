import * as L from "leaflet"
import { getPageTitle } from "../_title.js"
import { focusManyMapObjects, focusMapObject } from "../leaflet/_focus-layer-util.js"
import { getBaseFetchController } from "./_base-fetch.js"
import { initializeElementContent } from "./_element.js"
import { routerNavigateStrict } from "./_router.js"

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

        // TODO: Handle not found
        // if (!sidebarTitleElement.dataset.params) return

        const versionSections = sidebarContent.querySelectorAll(".version-section")
        const versionElements = []

        for (const versionSection of versionSections) {
            const elements = initializeElementContent(map, versionSection)
            versionElements.push(elements)

            // On mouse enter, focus elements
            const onVersionMouseEnter = () => {
                console.debug("onVersionMouseEnter")
                focusManyMapObjects(map, elements)
            }

            // On mouse leave, remove focus
            const onVersionMouseLeave = () => {
                console.debug("onVersionMouseLeave")
                focusMapObject(map, null)
            }

            // On click, navigate to version
            const onVersionClick = (e) => {
                const target = e.target
                if (target.closest("a, button, details")) return

                console.debug("onVersionClick")
                const { type, id, version } = JSON.parse(versionSection.dataset.params)
                const path = `/${type}/${id}/history/${version}`
                routerNavigateStrict(path)
            }

            // Listen for events
            versionSection.addEventListener("mouseenter", onVersionMouseEnter)
            versionSection.addEventListener("mouseleave", onVersionMouseLeave)
            versionSection.addEventListener("click", onVersionClick)
        }
    }

    const base = getBaseFetchController(map, "element-history", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = ({ type, id }) => {
        const url = `/api/partial/element/${type}/${id}/history${location.search}`
        baseLoad({ url })
    }

    base.unload = () => {
        focusMapObject(map, null)
        baseUnload()
    }

    return base
}
