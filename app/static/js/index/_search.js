import i18next from "i18next"
import * as L from "leaflet"
import { qsEncode, qsParse } from "../_qs.js"
import { getPageTitle } from "../_title.js"
import { focusManyMapObjects, focusMapObject } from "../leaflet/_focus-layer.js"
import { getBaseFetchController } from "./_base-fetch.js"

const searchInput = document.querySelector(".search-form").elements.q

/**
 * Create a new search controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getSearchController = (map) => {
    const defaultTitle = i18next.t("site.search.search")

    const onLoaded = (sidebarContent) => {
        const searchList = sidebarContent.querySelector(".search-list")
        const groupedElements = JSON.parse(searchList.dataset.leaflet)
        const results = searchList.querySelectorAll(".social-action")

        for (let i = 0; i < results.length; i++) {
            const elements = groupedElements[i]
            const result = results[i]

            // On mouse enter, focus elements
            const onResultMouseEnter = () => {
                console.debug("onResultMouseEnter")
                focusManyMapObjects(map, elements)
            }

            // On mouse leave, remove focus
            const onResultMouseLeave = () => {
                console.debug("onResultMouseLeave")
                focusMapObject(map, null)
            }

            // Listen for events
            result.addEventListener("mouseenter", onResultMouseEnter)
            result.addEventListener("mouseleave", onResultMouseLeave)
        }
    }

    const base = getBaseFetchController(map, "search", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = () => {
        const searchParams = qsParse(location.search.substring(1))
        const query = searchParams.q || searchParams.query || ""

        // Pad the bounds to gather more local results
        const bbox = map.getBounds().pad(1).toBBoxString()

        // Set page title
        document.title = getPageTitle(query || defaultTitle)

        // Set search input if unset
        if (!searchInput.value) searchInput.value = query

        const url = `/api/partial/search?${qsEncode({ q: query, bbox })}`
        baseLoad({ url })
    }

    base.unload = () => {
        baseUnload()
    }

    return base
}
