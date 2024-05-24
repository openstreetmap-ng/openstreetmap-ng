import i18next from "i18next"
import * as L from "leaflet"
import { qsEncode, qsParse } from "../_qs.js"
import { getPageTitle } from "../_title.js"
import { getMarkerIcon } from "../leaflet/_utils.js"
import { getBaseFetchController } from "./_base-fetch.js"

/**
 * Create a new search controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getSearchController = (map) => {
    const defaultTitle = i18next.t("site.search.search")

    const onLoaded = (sidebarContent) => {
        const resultActions = sidebarContent.querySelectorAll(".result-action")

        for (const resultAction of resultActions) {
            // Get params
            const dataset = resultAction.dataset
            const lon = Number.parseFloat(dataset.lon)
            const lat = Number.parseFloat(dataset.lat)
            let marker = null

            // On hover, show a marker
            const onResultActionMouseEnter = () => {
                if (!marker) {
                    marker = L.marker(L.latLng(lat, lon), {
                        icon: getMarkerIcon("red", true),
                        keyboard: false,
                        interactive: false,
                    })
                }

                map.addLayer(marker)
            }

            // On hover end, remove the marker
            const onResultActionMouseLeave = () => {
                map.removeLayer(marker)
            }

            // Listen for events
            resultAction.addEventListener("mouseenter", onResultActionMouseEnter)
            resultAction.addEventListener("mouseleave", onResultActionMouseLeave)
        }
    }

    const base = getBaseFetchController(map, "search", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = () => {
        const searchParams = qsParse(location.search.substring(1))
        const query = searchParams.query || ""

        // Set page title
        document.title = getPageTitle(query || defaultTitle)

        const url = `/api/partial/search?${qsEncode({ query })}`
        baseLoad({ url })
    }

    base.unload = () => {
        baseUnload()
    }

    return base
}
